#!/usr/bin/python

# True if you don't run as root (you shouldn't run as root)
# be sure to add something like the following to your sudoers file:
# yourusername ALL=NOPASSWD:/etc/init.d/httpd
USE_SUDO=False

SERVICES= {
	# Edit these services to match the ones you want to manage
	'apache2': {
		'title': 'Apache Web Server',
		'ops': ['status', 'stop','start','graceful'],
		'status': 'status'
	},
	'ssh': {
		'title': 'SSH Server',
		'ops': ['status','stop','start','restart'],
		'status': 'status'
	},
}

LOGINS = {
	# username and password hash
	# Generate new password hashes by running ./webinitd.py --password yourpasswordhere
	'admin': 'sha256:1024:C6vwpHVe:H9QumIJLvdQeb7ZR2izY092umM9TPqPlgVaPZRGeZiY=',
}


if __name__=="__main__":
	import app
	app.run(USE_SUDO,SERVICES,LOGINS)
