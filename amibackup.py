# Automated AMI Backups
#
# This script will search for all instances having a tag name with "BKUP"
# with value of "TRUE". As soon as we have the instances list, we loop through
# each instance and create an AMI of it.
#
# After creating the AMI it creates a "DeleteOn" tag on the AMI indicating when
# it will be deleted using the Retention value and another Lambda function
#If Ami is created on 1st date of any month then that Ami will get "DeleteOn"
#value of 90 days.
#If Ami is created on 31st December then that Ami will get "DeleteOn"
#value of 365*7 days.
#If Ami is created on any other date then that Ami will get "DeleteOn"
#value of 30 days.

import boto3
import collections
import jmespath
import datetime

ec = boto3.client('ec2')


def lambda_handler(event, context):
    reservations = ec.describe_instances(
        Filters=[
            {'Name': 'tag:BKUP', 'Values': ['TRUE']},
        ]
    ).get(
        'Reservations', []
    )

    found_instances = sum(
        [
                [i for i in r['Instances']]
                for r in reservations], []
    )

    #print "Found %d instances that need backing up" % len(instances)

    ami_ids = []
    instancenames = []
    is_aem = []

    # for every instance that needs to be dealt with:
    for instance in found_instances:
        # clean up our tag name
        name = str(jmespath.search("Tags[?Key=='Name'].Value ", instance)).strip('[]')
        name = str(name).strip("''")
        # add to our list of names
        instancenames.append(name)

        #find which instances are AEM so we can change the retention days dynamically
        if 'AEM' in str(jmespath.search("Tags[?Key=='Application'].Value ", instance)).strip('[]'):
            is_aem.append(True)
        else:
            is_aem.append(False)

        try:
            retention_days = [
                int(t.get('Value')) for t in instance['Tags']
                if t['Key'] == 'Retention'][0]
        except IndexError:
            retention_days = 30
            create_time = datetime.datetime.now()
            create_fmt = create_time.strftime('%Y-%m-%d')
            date_number = create_fmt.split("-")[2]
            month_number = create_fmt.split("-")[1]
			
            AMIid = ec.create_image(InstanceId=instance['InstanceId'],
                                    Name=name + "_" + create_time.strftime('%Y-%m-%d_%a'),
                                    Description="Lambda created AMI of instance " + instance['InstanceId'],
                                    NoReboot=True,
                                    DryRun=False)

            ami_ids.append(AMIid['ImageId'])
            

    for index, ami in enumerate(ami_ids):
	
	    if date_number=='01':
	        delete_date = datetime.date.today() + datetime.timedelta(days=90)
	    elif date_number=='31' and month_number=='12':
		    delete_date = datetime.date.today() + datetime.timedelta(days=365*7)
	    else:
	        
	        delete_date = datetime.date.today() + datetime.timedelta(days=retention_days)
	            
	    delete_fmt = delete_date.strftime('%m-%d-%Y')
	    ec.create_tags(Resources=[ami],
                       Tags=[
                             {'Key': 'DeleteOn', 'Value': delete_fmt},
                             {'Key': 'Name', 'Value': instancenames[index] + "_" + create_time.strftime('%Y-%m-%d_%a')}
                            ],
                       DryRun=False)
