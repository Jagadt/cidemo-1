import os
import sys
import time
import json
import yaml
import subprocess

USERS_LIST = {
'nirmal@cts.com': 12,
'akruthi@cts.com': 13,
'jaggi@cts.com': 14
}

DEV_FARM_ID = 8
PRIVATE_KEY = '/var/lib/jenkins/.ssh/FARM-8-410c49e8.us-east-1.pem'
STAGING_IP = "54.165.178.220"
STAGING_FARM_ID = "9"


def get_user_by_commit(hash):
        print("Get user by commit for hash: %s" % hash)
        out = subprocess.check_output(['git', 'show', os.environ.get('GIT_COMMIT'), '--name-only']).splitlines()
        index = 2 if out[1].strip().startswith('Merge') else 1
        author_email = out[index].split()[-1][1:-1]
        print("Commit author email: %s" % author_email)
        return author_email

def set_farm_owner(farm_id, farm_name, owner):
        print("Set owner %s to farm_id %s" % (owner, farm_id))
        with open('/var/lib/jenkins/workspace/scalr-jenkins/farm_update.json', 'r') as f:
                proto = json.load(f)
                with open('/tmp/farm_update_%s.json' % farm_id, 'w+') as f:
                        proto['name'] = farm_name
                        proto['owner']['id'] = USERS_LIST[owner]
                        proto['owner']['email'] = owner
                        f.write(json.dumps(proto))
                        subprocess.check_call('scalr-ctl farms update --farmId %s --stdin < /tmp/farm_update_%s.json' % (farm_id, farm_id), shell=True)

def clone_farm(farm_id, farm_name):
        print("Clone farm %s to new with name %s" % (farm_id, farm_name))
        out = yaml.load(subprocess.check_output(['scalr-ctl', 'farms', 'clone', '--name', farm_name, '--farmId',
        str(farm_id)]))
        print("New farm id is %s" % out['id'])
        return out['id']
def wait_server(farm_id):
        print("Run farm: %s" % farm_id)
        subprocess.check_call(['scalr-ctl', 'farms', 'launch', '--farmId', str(farm_id)])
        servers_count = 0
        print('Wait server in running in farm_id: %s' % farm_id)
        while servers_count != 1:
                out = json.loads(subprocess.check_output(['scalr-ctl', 'farms', 'list-servers', '--farmId', str(farm_id),'--json']))
                for serv in out['data']:
                        if serv['status'] != 'running':
                                print("Server %s in farm not in Running state, wait 15 seconds" % serv['id'])
                                time.sleep(15)
                        else:
                                return serv['publicIp'][0]

def upload_archive(server_ip, hash, staging=False):
        print('Upload archive with data to server')
        key = "/var/lib/jenkins/.ssh/staging.pem" if staging else "/var/lib/jenkins/.ssh/devel.pem"
        subprocess.check_call("scp -i %s /tmp/%s.tar.gz scalr@%s:/tmp/" % (key, hash, server_ip),shell=True)
        subprocess.check_call("ssh -i %s scalr@%s \"sudo rm -rf /var/www/html/* && sudo tar xzf /tmp/%s.tar.gz -C /var/www/html\"" % (key, server_ip, hash), shell=True)



def run_tests(server_ip):
        print('Run tests ')
        subprocess.check_output("ssh -i %s scalr@%s \"sudo python /var/www/html/tests.py\"" %(PRIVATE_KEY, server_ip), shell=True)
        print("Test finish success")

def terminate_farm(farm_id):
        print("Terminate farm: %s" % farm_id)
        subprocess.check_call(['scalr-ctl', 'farms', 'terminate', '--farmId', str(farm_id)])

def prepare_new_dev_farm(hash):
        #farm_name = os.environ.get('GIT_BRANCH') + '-%s' % hash[:7]
        farm_name = 'temp_farm' + '-%s' % hash[:7]
        if farm_name.startswith('origin'):
                farm_name = farm_name[7:]
                user = get_user_by_commit(hash)
                new_farm_id = clone_farm(DEV_FARM_ID, farm_name)
                set_farm_owner(new_farm_id, farm_name, user)
                server_ip = wait_server(new_farm_id)
                upload_archive(server_ip, hash)
                try:
                        run_tests(server_ip)
                except:
                        print("ERROR: Test failed!")
                        sys.exit(1)
                finally:
                        terminate_farm(new_farm_id)

def rename_farm(farm_id, farm_name, env):
        print("Rename farm %s to new name: %s" % (farm_id, farm_name))
        out = json.loads(subprocess.check_output("scalr-ctl farms get --farmId %s --envId %s --json" %(farm_id, env), shell=True))
        with open('/tmp/rename_farm_%s.json' % farm_name, 'w+') as f:
                out['data']['name'] = farm_name
                f.write(json.dumps(out['data']))
                subprocess.check_call("scalr-ctl farms update --envId %s --farmId %s --stdin </tmp/rename_farm_%s.json" % (env, farm_id, farm_name), shell=True)

def prepare_staging_farm(hash):
        prepare_new_dev_farm(hash)
        upload_archive(STAGING_IP, hash, staging=True)
        rename_farm(STAGING_FARM_ID, 'staging-%s' % hash[:7], 11)

if __name__ == '__main__':
        command = sys.argv[1]
        args = sys.argv[2:]
        globals().get(command)(*args)	
