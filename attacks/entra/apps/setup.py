import asyncio
import configparser
from configparser import SectionProxy
from azure.identity.aio import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.models.user import User
from msgraph.generated.models.password_profile import PasswordProfile
from msgraph.generated.models.o_data_errors.o_data_error import ODataError
from msgraph.generated.models.application import Application
from msgraph.generated.models.app_role_assignment import AppRoleAssignment
from msgraph.generated.models.service_principal import ServicePrincipal
from msgraph.generated.models.reference_create import ReferenceCreate
from msgraph.generated.models.unified_role_assignment import UnifiedRoleAssignment
from msgraph.generated.applications.item.add_password.add_password_post_request_body import AddPasswordPostRequestBody
from msgraph.generated.models.password_credential import PasswordCredential
from msgraph.generated.models.required_resource_access import RequiredResourceAccess
from msgraph.generated.models.resource_access import ResourceAccess
import time
from datetime import datetime
from faker import Faker
from uuid import UUID

class Setup:
    settings: SectionProxy
    client_credential: ClientSecretCredential
    app_client: GraphServiceClient

    def __init__(self, config: SectionProxy):
        self.settings = config
        client_id = self.settings['clientId']
        tenant_id = self.settings['tenantId']
        client_secret = self.settings['clientSecret']

        self.client_credential = ClientSecretCredential(tenant_id, client_id, client_secret)
        self.client = GraphServiceClient(self.client_credential) # type: ignore


    async def create_user(self):

        fake = Faker()
        name = fake.name()
        display_name = name+" (created by Hackbot)"
        mail_nickname = name.replace(" ", "")

        domain = await self.get_domain()
        user_principal_name = f"{mail_nickname.lower()}@{domain}"
        body = User(
            account_enabled = True,
            display_name = display_name,
            mail_nickname = mail_nickname,
            user_principal_name = user_principal_name,
            password_profile = PasswordProfile(
                force_change_password_next_sign_in = True,
                password = str(hex(hash(display_name))) +'123!',
            ),
        )

        result = await self.client.users.post(body)

        print(f'created user!')
        print(f' - display_name = {result.display_name}') 
        print(f' - object_id = {result.id}')
        return result.id


    async def get_internal_app_id(self, app_id):
        result = await self.client.applications_with_app_id(app_id).get()
        return result.id
        

    async def create_app(self):
        uniq = str(hex(hash(datetime.now())))[-8:-1]
        # make app
        request_body = Application(
            display_name = f"Test App {uniq} (created by Hackbot)"
        )

        app = await self.client.applications.post(request_body)
        app_object_id = app.id
        app_client_id = app.app_id
        

        request_body = ServicePrincipal(
            app_id = app_client_id,
        )

        sp = await self.client.service_principals.post(request_body)
        sp_id = sp.id

        await self.create_app_creds(app_object_id, app_client_id)

        print(f'created app!')
        print(f' - display_name = {app.display_name}')
        print(f' - client_id={app_client_id}')
        print(f' - object_id={app_object_id}')
        print(f' - service_principal_id={sp_id}')
        
        return (app_object_id, app_client_id, sp_id)

    async def get_sp_by_app(self, app_id):
        result = await self.client.service_principals_with_app_id(app_id).get()
        return result

    async def add_api_permissions(self, app_id, principal_id, perms):
        d = {}
        for p in perms:
            elems = d.get(p[0], [])
            elems.append(p[1])
            d[p[0]] = elems

        rra = []
        for key in d:
            ras = []
            for p in d[key]:
                ras.append(ResourceAccess(id=UUID(p), type="Role"))
            
            rra.append(
                RequiredResourceAccess(
                    resource_app_id=key,
                    resource_access = ras
                )
            )

        request_body = Application(
            required_resource_access=rra
        )
        await self.client.applications.by_application_id(app_id).patch(request_body)

        for p in perms:
            resource_app_id = p[0]
            permission_id = p[1]
            sp = await self.get_sp_by_app(resource_app_id)
            resource_sp_id = sp.id
            # now we have the SP, assign it the api permission
            request_body = AppRoleAssignment(
                principal_id = UUID(principal_id),
                resource_id = UUID(resource_sp_id),
                app_role_id = UUID(permission_id),
            )

            await self.client.service_principals.by_service_principal_id(principal_id).app_role_assignments.post(request_body)

        return

    async def get_tenant_id(self):
        res = await self.client.organization.get()
        return res.value[0].id

    async def get_domain(self):
        res = await self.client.domains.get()
        return res.value[0].id

    async def create_app_creds(self, app_id, client_id):
        request_body = AddPasswordPostRequestBody(
            password_credential = PasswordCredential(
                display_name = "Created by hackbot",
            ),
        )
        result = await self.client.applications.by_application_id(app_id).add_password.post(request_body)

        tenant_id = await self.get_tenant_id()
        with open("exploit.cfg", "w") as f:
            cfg = f"""
[azure]
clientId = {client_id}
clientSecret = {result.secret_text}
tenantId = {tenant_id}
            """
            f.write(cfg)
            f.close()

    async def make_user_app_owner(self, user_id, app_id):

        request_body = ReferenceCreate(
            odata_id = f"https://graph.microsoft.com/v1.0/directoryObjects/{user_id}",
        )

        await self.client.applications.by_application_id(app_id).owners.ref.post(request_body)

    async def assign_user_directory_role(self, principal_id, role_id):
            request_body = UnifiedRoleAssignment(
                odata_type = "#microsoft.graph.unifiedRoleAssignment",
                role_definition_id = role_id,
                principal_id = principal_id,
                directory_scope_id = "/",
            )
            await self.client.role_management.directory.role_assignments.post(request_body)

    async def teardown(self, app_id, sp_id, user_id):
        if sp_id:
            await self.client.service_principals.by_service_principal_id(sp_id).delete()
        if app_id:
            await self.client.applications.by_application_id(app_id).delete()
        if user_id:
            await self.client.users.by_user_id(user_id).delete()


async def main():

    # Load settings
    config = configparser.ConfigParser()
    config.read(['setup.cfg'])
    azure_settings = config['azure']

    bot: Setup = Setup(azure_settings)
    
    print('')
    print('enter app client id, leave blank to create app:')
    
    choice = str(input())
    app_client_id = None
    app_object_id = None
    sp_id = None
    if choice == "":
        (app_object_id, app_client_id, sp_id) = await bot.create_app()
    else:
        app_client_id = choice
        try:
            app_object_id = await bot.get_internal_app_id(app_client_id)
        except Exception as e:
            raise ValueError('cannot find app client id!') from e

        try:
            sp_id = await bot.get_sp_by_app(app_client_id)
            print(f'found service principal: {sp_id}')
        except Exception as e:
            raise ValueError('cannot find service principal from provided app client id') from e
    


    perms = []
    while True:
        print('')
        print('add permission to the app, leave blank to skip: ({resource_app_id} {permission_id})')
        print('e.g. (00000003-0000-0000-c000-000000000000 9e3f62cf-ca93-4989-b6ce-bf83c28f9fe8) to add "Microsoft Graph" app API permission "RoleManagement.ReadWrite.Directory"')
        choice = str(input())

        parts = choice.split(" ")
        if len(parts) < 2:
            break

        resource_id = parts[0]
        permission_id = parts[1]

        perms.append((resource_id, permission_id))
    
    if len(perms) > 0:
        await bot.add_api_permissions(app_object_id, sp_id, perms)

    print(f'added permissions!')
    print('if admin approval required, please visit: https://login.microsoftonline.com/common/adminconsent?client_id={app_client_id}')


    print('')
    print('please enter user object id who will manage the app, leave blank to create: ')
    print('(if you wish to skip this stage, enter "n")')
    user_choice = str(input())
    user_id = None
    if user_choice == "n":
        pass
    elif user_choice == "":
        user_id = await bot.create_user()
        time.sleep(3)
        
    else:
        user_id = user_choice


    choice = ""
    if user_choice != "n":
        print('')
        print('how should this user manage the app?')
        print('(1=Owner, 2=Application Administrator, 3=Cloud Application Administrator)')
        choice = str(input())
    
    elif choice == "1":
        await bot.make_user_app_owner(user_id, app_object_id)
    elif choice == "2":
        await bot.assign_user_directory_role(user_id, "9b895d92-2cd3-44c7-9d02-a6ac2d5ea5c3")
    elif choice == "3":
        await bot.assign_user_directory_role(user_id, "158c047a-c907-4556-b7ef-446551a6b5f7")
    

    print('finished setup!')
    print('remove all created resources? (y/n)')
    choice = str(input())
    if choice == "y":
        await bot.teardown(app_object_id, sp_id, user_id)
    
    print("done!")
asyncio.run(main())