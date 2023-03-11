Provides text-based alerts for users based on their personal COVID risk level based on county. This is a public version of my private COVID-Alert repository.

Data is obtained from: https://covid.cdc.gov/covid-data-tracker/#datatracker-home

New users can be added with the Subscriber.create() method, or by adding them to subscribers.csv. All new users should be initialized with 0 for any numerical value and 'Unknown' for any alphabetical value.

Before running the software you will need to add your Twilio credentials to config.txt. This alert is best scheduled to run once a week at the end of the week, as the CDC typically updates the data once a week on Thursday or Friday.