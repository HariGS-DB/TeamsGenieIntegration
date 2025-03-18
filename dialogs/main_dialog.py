# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os

from botbuilder.core import MessageFactory
from botbuilder.dialogs import (
    WaterfallDialog,
    WaterfallStepContext,
    DialogTurnResult,
    PromptOptions,
)
from botbuilder.dialogs.prompts import OAuthPrompt, OAuthPromptSettings, ConfirmPrompt

import bots.teams_bot
import config
from config import DefaultConfig
from dialogs import LogoutDialog
CONFIG = DefaultConfig()

class MainDialog(LogoutDialog):
    def __init__(self, connection_name: str):
        super(MainDialog, self).__init__(MainDialog.__name__, connection_name)

        self.add_dialog(
            OAuthPrompt(
                OAuthPrompt.__name__,
                OAuthPromptSettings(
                    connection_name=connection_name,
                    text="Please Sign In",
                    title="Sign In",
                    timeout=300000,
                ),
            )
        )

        self.add_dialog(ConfirmPrompt(ConfirmPrompt.__name__))

        self.add_dialog(
            WaterfallDialog(
                "WFDialog",
                [
                    self.prompt_step,
                    self.login_step
                ],
            )
        )

        self.initial_dialog_id = "WFDialog"

    async def prompt_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        return await step_context.begin_dialog(OAuthPrompt.__name__)

    async def login_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        token = step_context.result.__dict__["token"]
        user_id = step_context.context.activity.from_property.id
        bots.teams_bot.DATABRICKS_TOKEN[user_id] = token

        # Get the token from the previous step. Note that we could also have gotten the
        # token directly from the prompt itself. There is an example of this in the next method.
        if step_context.result:
            await step_context.context.send_activity("You are now logged in.")
            return await step_context.end_dialog(result=token)

        await step_context.context.send_activity(
            "Login was not successful please try again."
        )
        return await step_context.end_dialog()
