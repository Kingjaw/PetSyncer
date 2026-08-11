# PetSyncer
This is a tool for syncing data between PetPoint and RescueGroups.
The tool runs at 5:30 AM every day, and emails the outbound email with an output log. These output logs are also saved on this page as artifacts.
The output logs will display the following information in order:

**Missing RescueIDs**
Pets with no RescueID in RescueGroups.

**Discrepancies**
The discrepancies in status between RescueGroups and Petpoint.

**Records created**
When a new record can be created in Rescuegroups, it will be noted here. It follows this up with a list of all the data taken from petpoint, and a log directly from the RescueGroups API.

**Errors**
If the program ever completely fails, there will be no output log or email made to the outbound email. It will instead email me with a failure log. Sometimes, there will be incomplete data in petpoint, such as a missing gender. In this case, the program will still run fine but it won't create a new record in RescueGroups until all the necessary data is there. This will show up under "errors found" in the output.txt in the email.
