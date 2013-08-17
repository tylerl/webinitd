import os
import pty
import errno
import fcntl
import select
#import subprocess

def run(*args):
	'''
	Runs the command specified by `*args`, capturing both stdout and stderr. Both
	outputs go into an array as strings tagged with the propety "source" containing
	the value either "stdout" or "stderr".

	>>> out = run("/bin/ls")
	>>> for item in out:
	...   print(item.source + ": " + item)
	stdout: foo.txt bar.txt

	The program runs attached to a pty so that the output will be line-buffered
	instead of block-buffered. This helps preserve the ordering of stdout/stderr text.
	'''

	err_r,err_w = os.pipe()
	output_lines=[]

	forkpid, forkfd = pty.fork()
	if forkpid==0:  # child process
		os.dup2(err_w,2)  # replace stderr
		os.close(0)
		os.execv(args[0],args)
		raise OSError("Failed exec")
		# notreached

	os.close(err_w)  # not ours

	poll=select.poll()
	fdmap = { 
		forkfd: _append_tag(output_lines,"stdout"),
		err_r: _append_tag(output_lines,"stderr"),
	}
	POLL_INPRI = select.POLLIN | select.POLLPRI
	poll.register(forkfd, POLL_INPRI)
	poll.register(err_r, POLL_INPRI)

	def close_and_remove(fd):
		poll.unregister(fd)
		os.close(fd)
		fdmap.pop(fd)

	while fdmap and poll:
		try:
			ready = poll.poll()
		except select.error as e:
			if e.args[0] == errno.EINTR:
				continue
			raise
		for fd, mode in ready:
			if mode & POLL_INPRI:
				data = os.read(fd,4096)
				if data:
					fdmap[fd](data)
				else:
					close_and_remove(fd)
			else:
				close_and_remove(fd)
	os.waitpid(forkpid,0)
	return output_lines

##################################################################

def _append_tag(list_,tag):
	class _str(str):
		source=tag
	def fn(s):		
		list_.append(_str(s))
	return fn

def set_close_exec(fd):
	old = fcntl.fcntl(fd,fcntl.F_GETFD)
	fcntl.fcntl(fd,fcntl.F_SETFD, old | fcntl.FD_CLOEXEC)

