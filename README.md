# GenieTeamsIntegration

## Objective

This project implements an experimental chatbot that interacts with Databricks' Genie API, which is currently in Public Preview.
The bot is designed to facilitate conversations with Genie, Databricks' AI assistant, through a chat interface like MS Teams.

## Overview

This experimental code creates a Genie BOT in Databricks using the Genie API. It's important to note that this is not production-ready code and is not associated with or endorsed by any employer.
The code is intended to be used as-is for experimental and learning purposes only.

## Key Features

- Integrates with Databricks' Genie API to start conversations and process follow-up messages
- Allows user to authenticate to IDP and uses user token to connect to Genie
- Formats and displays query results in a readable markdown table

## Components Requires

- Create a App Service Plan
- Create a Web App
- Create a Azure Bot
- Create Entra Application with configuration
- App Manifest to create a Teams App

## Implementation Details

### Azure Resources

1. Create App Service Plan
2. Create Web App on the App Service Plan
3. Add Configuration to the web app - "gunicorn --bind 0.0.0.0 --worker-class aiohttp.worker.GunicornWebWorker --timeout 1200 app:app"
4. Create Azure Bot
5. Add webapp endpoint details to Azure Bot: <WebApp Endpoint>/api/messages

### Azure Entra Application Configuration

1. Open the Entra appliation created from the Azure Bot
2. Go to authentication and add Web redirect url as `<https://token.botframework.com/.auth/web/redirect>`
3. Go Expose an API:

- Click Add application URI and enter the uri in the format: `api://botid-<GeneratedID>`
- Add a scope:
  - name of scope "scope_as_user"
  - Who can consent: Admin and Users
  - Admin consent display name: "Teams can access User Profile"
  - Admin consent description: "Teams can access User Profile"
  - User consent display name: "Teams can access User Profile and make request on behalf of the User"
  - Click save
- Under authorized client application, click add application:
  - add 5e3ce6c0-2b1f-4285-8d4b-75ee78787346 (Teams web application) and select the created scope
  - add 1fec8e78-bce4-4aaf-ab1b-5451cc387264 (Teams desktop/mobile application) and select the created scope

4. Go to API permissions and add the following permissions:

- Azure Databricks -> User Impersonation
- Microsoft Graph  -> email, openid, offline_access, profile, User.Read

For more details refer <https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/authentication/bot-sso-register-aad?tabs=botid>

### Configure OAuth setting in Bot

1. Go to the Azure Bot under configuration
2. Click Add OAuth Connection Settings and add the following

- Name: TeamsAuth
- Service Provider: Azure Active Directory V2
- Client ID: client id of the azure bot application
- Client Secret: secret of the azure bot application configured previously
- token exchange url: the application url entered in step 3a above
- Tenant ID: tenant id of the azure bot application
- scope: 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default

### Deploy Web app

1. Install the required dependencies listed in `requirements.txt`
2. Open config.py and update the values for `APP_ID` with bot app id, `APP_PASSWORD` with bot app secret and
connection name with `TeamsAuth` (name given in bot OAuth Setting)
3. Deploy the code to the web app using the cmd below (ensure you have az cli with login available):

```sh
az webapp up --name <your-app-name> --resource-group <your-resource-group> --plan <your-app-service-plan> --runtime "PYTHON:3.10" --sku <AppServicePlanSKU>
```

## Integrating with MS Teams

1. open the manifest file under appManifest--> manifest.json
2. replace the following values with the azure bot app id

- id: app id
- bots.botId: app id
- webApplicationInfo.Id: app id
- webApplicationInfo.resource: `api://botid-<APPID>>`

3. navigate to `appManifest` folder and zip the files using `zip genie.zip ./*`
4. Open MS Teams : You should be a Teams Admin to add a custom app
5. Go to Apps-->Manage your App--> Upload and App-->Upload a Custom App and select and upload the zip file

## Automated using Terraform

The required Azure resources can be automatically deployed using Terraform.

Inside `terraform` folder, create a `auo.tfvars` file, specifying

```tf
prefix          = # prefix for all resources
location        = # location of all resources
tenant_id       = # AAD tenant id
subscription_id = # Azure subscription id
```

Then run `terraform apply`. The necessary resources will be deloyed, and 2 additional files will be created:

- `deploy.sh`: contains the `az` command to deploy the web app
- `manifest.json` in `appManifest` folder: contains the manifest to deploy the Teams app.
