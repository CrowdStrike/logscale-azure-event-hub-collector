![CrowdStrike FalconPy](https://raw.githubusercontent.com/CrowdStrike/falconpy/main/docs/asset/cs-logo.png)

# Azure Function Deployment Steps using ARM template
- To populate dashboards in LogScale, you need to deploy Function app in Azure
- Configure function app via ARM template following the below steps:

   - Download the [arm.json](arm.json) file.
   - Go to [Azure Portal](portal.azure.com)
   - Search for `Deploy a custom template`
   - Select `Build your Own Template`
   - Load the ARM.json file

- After loading need to specify all the project details and Instance details to deploy. Ensure the following fields are entered correctly
   - Resource Group
   - Function Name(Default- LogScale)
   - Eventhub Namespace
   - Eventhub Name
   - Shared Access Key(From Eventhub Namespace ->Settings -> Shared Access Policy -> your Policy -> `primary key`)
   - LogScalehostname(e.g. :-https://cloud.community.humio.com/)
   - LogScaletoken(Parser token)
   - FunctionJobSchedule(Cron job scheduler)
- After that go to [Azure](portal.azure.com) search for `function app` 
- Select Your function App Name and Start function app to collect logs in LogScale instance.
