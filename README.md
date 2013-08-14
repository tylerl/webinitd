webinitd
========

Allows you to run `init.d` actions from a nifty web interface. Set up the allowed
services like so:

	SERVICES= {
		'apache2': {                        # the name of the /etc/init.d/ file
			'title': 'Apache Web Server',   # the name you want displayed
			'ops': ['status', 'stop','start','graceful'],  # allowed commands
			'status': 'status'              # The "default" command to show on the main listing
		},

For priv elevation, set `USE_SUDO=True`, and don't forget to update your sudoers file accordingly.
E.g. 

    youruser ALL=NOPASSWD:/etc/init.d/apache2
    youruser ALL=NOPASSWD:/etc/init.d/mysqld
	... etc.


Next get your authentication in order. Run the app like this:

    ./webinitd.py --password=my_password

That'll spit out a password hash that you put into your auth dict that looks like this:

	LOGINS = {
		'admin': 'sha256:10240:FcbYJZ4Z:ZDHbf8Gx/GDXVD3W33xjqnEuf3TWv41rGrSig8fM7d4=',
	}


Finally, run webinitd.py and hit it with your browser with the optional `-h` and `-p`
parameters to specify a host and port.
