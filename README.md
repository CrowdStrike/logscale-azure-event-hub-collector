![CrowdStrike FalconPy](https://raw.githubusercontent.com/CrowdStrike/falconpy/main/docs/asset/cs-logo.png)

# LogScale Azure Event Hub Collector
This Azure function provides the ingest method for the LogScale Marketplace package for Microsoft 365. The initial version of this package focuses on email security events. The function collects Microsoft 365 Defender email events from Event Hub and ingests this data to LogScale.  
If you are using this Azure function with the Microsoft 365 LogScale Marketplace package please refer to the documentation [here](https://library.humio.com/integrations-windows-microsoft-package-365) rather than the more generic and high level information included below.
The Azure function was built for and has been tested with collecting specific Microsoft 365 Defender email data from an Event Hub (as described in above documentation link) and this is the supported use case.  However, the Azure function could be used to collect other json format event data from Event Hub and ingest to LogScale. Below are generic instructions for how to install and configure this.
## Deploy and configure LogScale Azure Event Hub Collector


* Download the `ARM.json` file from the Release section and save it locally
* Go to [Azure Portal](portal.azure.com)
* Search for `Deploy a custom template`
* Select `Load file` and upload the ARM.json file
* Wait for the upload to complete 
* select `Save` 

Now enter the following configuration for the deployment:
* Subscription - select the subscription plan to use for this deployment
* Resource Group - select an existing resource group or add a new one if preferred
* Function Name - provide a name e.g. `LogScale`
* Eventhub Namespace - enter the Namespace for the Event Hub
* Eventhub Name - enter the Name for the Event Hub
* Shared Access Key - enter the `primary key` (From Eventhub Namespace ->Settings -> Shared Access Policy -> your Policy -> `primary key`)
* LogScale Host URL - enter the base URL of your LogScale service (e.g. cloud.us.humio.com)
* LogScale Ingest Token - enter a LogScale ingest token
* LogScale Schedule(Cron job) - enter a valid cron expression to determine how often the function is run.  (e.g. `0 0/5 0 ? * * *` would be to run every 5 minutes)
* Select `Review + create`

   Azure will validate the deployment and should indicate that the Validation Passed. Ensure you understand the terms and conditions and then 
   
   Select `Create`
   
   Various progress messages will display before it is indicated that the deployment is complete.


## Now start the function app
  - Go to [Azure](portal.azure.com) search for "function app"
  - Select your function `App Name` and `Start` the function app to send the logs to LogScale.

From the Function app navigate to Functions -> timetrigger -> monitor to check you can see the events in the monitor tab.


**NOTE** - use of Azure functions is chargeable and the pricing depends on a number of factors including your selected subscription plan. Please make sure you understand the cost impact of running this function.
