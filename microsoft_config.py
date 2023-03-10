# Contains settings for Web App


# This is for multi-tenant, alternatively set equal to "https://login.microsoftonline.com/<TENANT_ID>" for a single tenant
AUTHORITY = "https://login.microsoftonline.com/common"
#AUTHORITY = "https://login.microsoftonline.com/9a33e6c7-5e10-4230-a789-3ce21d3f1a0a" 
SCOPE = [
"Notes.Create",
"Notes.Read",
"Notes.Read.All",
"Notes.ReadWrite",
"Notes.ReadWrite.All",
"Notes.ReadWrite.CreatedByApp",
"User.ReadBasic.All"]
SESSION_TYPE = "filesystem"  # So the token cache will be stored in a server-side session
#REDIRECT_PATH = "http://localhost:5000/getAToken"
CLIENT_ID = "28fe51b5-e1d5-4e57-8b88-203f2ed1eb88"
SECRET_VALUE = "2m_8Q~kIcOZfUf6EggBZ.HKge~dDdzDu~hOUrb-u"
SECRET_ID = "413ca3cd-2507-4766-a22f-720672b8ef87"

