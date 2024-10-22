## What makes an App a security risk in Entra ID?

By granting Apps permissions they need to operate—especially for apps used to manage the directory itself—we can introduce the risk of creating unintended paths to privilege. 

In Entra ID, every App has a corresponding “service principal” attached to it. When a human performs actions within Entra, it does this using a user account. When an application performs actions within Entra, it does so using a service principal account. 

There are two key factors that make Apps and their associated Service Principals dangerous.

1. API Permissions

Apps commonly request API permissions to perform actions against the APIs of other apps. Some permissions can be used to do things within the Directory itself. Here are two particularly dangerous entitlements:

- RoleManagement.ReadWrite.Directory - Allows the app to read and manage the role-based access control (RBAC) settings for your company's directory, without a signed-in user. This includes instantiating directory roles and managing directory role membership, and reading directory role templates, directory roles and memberships.
- RoleAssignmentSchedule.ReadWrite.Directory - Allows the app to read, update, and delete policies for privileged role-based access control (RBAC) assignments of your company's directory, without a signed-in user.

2. Directory Roles

Just like users, service principals can be assigned roles in Entra, and some builtin directory roles are very powerful! For instance:
- Global Administrator
- Privileged Authentication Administrator
- Privileged Role Administrator
- Partner Tier2 Support
- Security Administrator
- Intune Administrator

All these directory roles, have roughly the same level of privilege as the Global Adminstator role, which is the highest privileged role, having permission to do everything. If any of our App’s service principals have a role listed above, it’s management must be carefully protected, as anyone who can manage the app essentially has these permissions too. This is because the human user controls the app, and, in essence, can make it do anything the service princiapl’s assigned role can perform.

## Demo

Warning! Running the setup creates insecure attack paths inside your Entra environment, this should be used in lab scenarios only.
In order to demonstrate the exploit we will create an app that is responsible for setting up the attack paths, give it sufficient privileges, and then run the app to perform the setup.

### Setup

1. Register an application in Entra ID (remember to delete after)
2. Grant application following api permissions
  - Application.ReadWrite.All
  - AppRoleAssignment.ReadWrite.All
  - Directory.ReadWrite.All
  - RoleManagement.ReadWrite.Directory
  - User.ReadWrite.All
3. Make credentials for the application
4. Put correct credentials in `setup.cfg`
5. Run `python setup.py`, follow prompts
  - create an app, or use an existing one
  - configure the app with api permissions to test out
  - if required, create a user who can manage the app


Example setup.cfg

```
[azure]
clientId = client_id_of_app
clientSecret = secret_from_step_3
tenantId = tenant_id_in_etra
```

## Exploit

1. Run `python exploit.py`, follow prompts...





