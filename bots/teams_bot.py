# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from typing import List
from botbuilder.core import (
    ConversationState,
    UserState,
    TurnContext,
)
from botbuilder.dialogs import Dialog
from botbuilder.schema import ChannelAccount

import bots
import config
from helpers.dialog_helper import DialogHelper
from .dialog_bot import DialogBot
from databricks.sdk import WorkspaceClient, GenieAPI
from typing import Dict, Optional
import asyncio
from msal import PublicClientApplication
import logging
import json

DATABRICKS_SPACE_ID = "01efe89b75951e8abea13c1057a09290"  # From your Genie Space URL - https://adb-<yourhost>.azuredatabricks.net/genie/rooms/<THIS_ONE_IS_YOUR_GENIE_SPACE_ID>/chats/<not_this_one>
DATABRICKS_HOST = (
    "https://adb-984752964297111.11.azuredatabricks.net/"  # From your Databricks URL
)
DATABRICKS_TOKEN = {}  # From the Settings in your Databricks workspace


# Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def ask_genie(
        question: str,
        space_id: str,
        workspace_client: WorkspaceClient,
        genie_api: GenieAPI,
        conversation_id: Optional[str] = None,
) -> tuple[str, str]:
    try:
        loop = asyncio.get_running_loop()
        if conversation_id is None:
            initial_message = await loop.run_in_executor(
                None, genie_api.start_conversation_and_wait, space_id, question
            )
            conversation_id = initial_message.conversation_id
        else:
            initial_message = await loop.run_in_executor(
                None,
                genie_api.create_message_and_wait,
                space_id,
                conversation_id,
                question,
            )

        query_result = None
        if initial_message.query_result is not None:
            query_result = await loop.run_in_executor(
                None,
                genie_api.get_message_query_result,
                space_id,
                initial_message.conversation_id,
                initial_message.id,
            )

        message_content = await loop.run_in_executor(
            None,
            genie_api.get_message,
            space_id,
            initial_message.conversation_id,
            initial_message.id,
        )

        if query_result and query_result.statement_response:
            results = await loop.run_in_executor(
                None,
                workspace_client.statement_execution.get_statement,
                query_result.statement_response.statement_id,
            )

            query_description = ""
            for attachment in message_content.attachments:
                if attachment.query and attachment.query.description:
                    query_description = attachment.query.description
                    break

            return json.dumps(
                {
                    "columns": results.manifest.schema.as_dict(),
                    "data": results.result.as_dict(),
                    "query_description": query_description,
                }
            ), conversation_id

        if message_content.attachments:
            for attachment in message_content.attachments:
                if attachment.text and attachment.text.content:
                    return json.dumps(
                        {"message": attachment.text.content}
                    ), conversation_id

        return json.dumps({"message": message_content.content}), conversation_id
    except Exception as e:
        logger.error(f"Error in ask_genie: {str(e)}")
        return json.dumps(
            {"error": "An error occurred while processing your request."}
        ), conversation_id


def process_query_results(answer_json: Dict) -> str:
    response = ""
    if "query_description" in answer_json and answer_json["query_description"]:
        response += f"## Query Description\n\n{answer_json['query_description']}\n\n"

    if "columns" in answer_json and "data" in answer_json:
        response += "## Query Results\n\n"
        columns = answer_json["columns"]
        data = answer_json["data"]
        if isinstance(columns, dict) and "columns" in columns:
            header = "| " + " | ".join(col["name"] for col in columns["columns"]) + " |"
            separator = "|" + "|".join(["---" for _ in columns["columns"]]) + "|"
            response += header + "\n" + separator + "\n"
            for row in data["data_array"]:
                formatted_row = []
                for value, col in zip(row, columns["columns"]):
                    if value is None:
                        formatted_value = "NULL"
                    elif col["type_name"] in ["DECIMAL", "DOUBLE", "FLOAT"]:
                        formatted_value = f"{float(value):,.2f}"
                    elif col["type_name"] in ["INT", "BIGINT", "LONG"]:
                        formatted_value = f"{int(value):,}"
                    else:
                        formatted_value = str(value)
                    formatted_row.append(formatted_value)
                response += "| " + " | ".join(formatted_row) + " |\n"
        else:
            response += f"Unexpected column format: {columns}\n\n"
    elif "message" in answer_json:
        response += f"{answer_json['message']}\n\n"
    else:
        response += "No data available.\n\n"

    return response


class TeamsBot(DialogBot):
    def __init__(
            self,
            conversation_state: ConversationState,
            user_state: UserState,
            dialog: Dialog,
    ):
        super(TeamsBot, self).__init__(conversation_state, user_state, dialog)
        self.conversation_ids: Dict[str, str] = {}
        self.workspace_client = {}

        self.genie_api = {}

    async def on_members_added_activity(
            self, members_added: List[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            # Greet anyone that was not the target (recipient) of this message.
            # To learn more about Adaptive Cards, see https://aka.ms/msbot-adaptivecards for more details.
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "Welcome to AuthenticationBot. Type anything to get logged in. Type "
                    "'logout' to sign-out. Test Teams bot"
                )

    async def on_teams_signin_verify_state(self, turn_context: TurnContext):
        # Run the Dialog with the new Token Response Event Activity.
        # The OAuth Prompt needs to see the Invoke Activity in order to complete the login process.
        await DialogHelper.run_dialog(
            self.dialog,
            turn_context,
            self.conversation_state.create_property("DialogState"),
        )

    async def on_message_activity(self, turn_context):
        user_id = turn_context.activity.from_property.id
        if turn_context.activity.text not in ("logout", "login"):
            question = turn_context.activity.text

            conversation_id = self.conversation_ids.get(user_id)
            try:
                if bots.teams_bot.DATABRICKS_TOKEN[user_id] != "":
                    if not self.workspace_client[user_id]:
                        self.workspace_client[user_id] = WorkspaceClient(
                            host=DATABRICKS_HOST,
                            token=bots.teams_bot.DATABRICKS_TOKEN[user_id],
                        )

                        self.genie_api[user_id] = GenieAPI(self.workspace_client[user_id].api_client)

                if not self.workspace_client[user_id].current_user.me():
                    await turn_context.send_activity(
                        "User is not added to Databricks workspace, Please get access and try again"
                    )
            except Exception as e:
                await turn_context.send_activity(
                    "Unable to login, Please type login to sign"
                )
                return
            try:
                answer, new_conversation_id = await ask_genie(
                    question,
                    DATABRICKS_SPACE_ID,
                    self.workspace_client[user_id],
                    self.genie_api[user_id],
                    conversation_id,
                )
                self.conversation_ids[user_id] = new_conversation_id

                answer_json = json.loads(answer)
                response = process_query_results(answer_json)

                await turn_context.send_activity(response)
            except json.JSONDecodeError:
                await turn_context.send_activity(
                    "Failed to decode response from the server."
                )
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await turn_context.send_activity(
                    "An error occurred while processing your request."
                )

        elif turn_context.activity.text in "logout":
            bots.teams_bot.DATABRICKS_TOKEN[user_id] = ""
            self.workspace_client[user_id] = None
            self.genie_api[user_id] = None
            return await super().on_message_activity(turn_context)

        else:
            return await super().on_message_activity(turn_context)
