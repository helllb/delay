#!/usr/bin/python3

from asynciojobs import Scheduler
from apssh import SshNode, SshJob, Run, RunString, Pull, Push

import numpy as np
import matplotlib.pyplot as plt
import json
import pingparsing

from time import sleep

import os
from argparse import ArgumentParser
import configparser

length = len

parser = ArgumentParser()
parser.add_argument("--pings", type=int, default=10000)

parser.add_argument("--setup", default=False, action='store_true')
parser.add_argument("--ntp", type=int, default=-1)
parser.add_argument("--run", type=str, default=None)
parser.add_argument("--analyse", default=False, action='store_true')
args = parser.parse_args()

config = configparser.ConfigParser()
config.read("ping.ini")

setup = args.setup
ntp = args.ntp
run = args.run
analyse = args.analyse
check = config['cluster']['check_lease'] == 'yes'

SLICE = config['cluster']['username']
HOSTNAME = config['cluster']['gw_hostname']

SERVER = config['cluster']['server_hostname']
CLIENT = config['cluster']['client_hostname']
SERVERADD = config['cluster']['server_address']
CLIENTADD = config['cluster']['client_address']
IMAGE = config['cluster']['image']
IFACE = config['cluster']['iface']

N = args.pings
if run == "default":
	RANGE = [98]
elif run == "sizes":
	RANGE = list(range(100, 1401, 100))
RANGE_ = '{' + ','.join([str(size - 42) for size in RANGE]) + ',}'

PATH = config['default']['path']

gateway = SshNode(hostname=HOSTNAME, username=SLICE, verbose=True)

server = SshNode(gateway=gateway, hostname=SERVER, username='root')
client = SshNode(gateway=gateway, hostname=CLIENT, username='root')


scheduler = Scheduler()

requirement = None

# preparing nodes
if check:
	check_lease = SshJob (
	        node = gateway,
	        critical = True,
	        commands = [
	        	# Run("rm tmp/*"),
	        	Run("rhubarbe leases --check")
	        ],
	        scheduler = scheduler
	)

	requirement = check_lease

if setup:
	load_images = SshJob (
			node = gateway,
			commands = [
				Run("rhubarbe load -i %s %s %s" % (IMAGE, SERVER, CLIENT)),
				Run("rhubarbe wait %s %s --timeout 120" % (SERVER, CLIENT)),
				
			],
			required = requirement,
			scheduler = scheduler
	)

	data01 = SshJob (
			node = server,
			commands = [
				Run("ifconfig %s %s/24 up" % (IFACE, SERVERADD)),
				Run("mkdir tests")
			],
			required = load_images,
			scheduler = scheduler
	)

	data02 = SshJob(
			node = client,
			commands = [
				Run("ifconfig %s %s/24 up" % (IFACE, CLIENTADD)),
				Run("mkdir tests")
			],
			required = load_images,
			scheduler = scheduler
	)

	requirement = (data01, data02)


if ntp > 0:
	ntp01 = SshJob(
			node = server,
			commands = [
				# Run("sed -i -e s/'broadcast 10.10.20.255'//g /etc/ntp.conf"),
				# Run("sed -i -e s/'listen on data'//g /etc/ntp.conf"),
				# Run("echo broadcast 10.10.20.255 >> /etc/ntp.conf"),
				# Run("echo listen on data >> /etc/ntp.conf"),
				# Run("service ntp restart")
				Push(localpaths=["ntp_server.conf"], remotepath="/etc/"),
				Run("mv /etc/ntp_server.conf ntp.conf"),
				Run("service ntp restart")
			],
			required = requirement,
			scheduler = scheduler
	)

	ntp02 = SshJob(
			node = client,
			commands = [
				# Run("sed -i -e s/'disable auth'//g /etc/ntp.conf"),
				# Run("sed -i -e s/broadcastclient//g /etc/ntp.conf"),
				# Run("sed -i -e s/'server 10.10.20.1 iburst'//g /etc/ntp.conf"),
				# Run("echo disable auth >> /etc/ntp.conf"),
				# Run("echo broadcastclient >> /etc/ntp.conf"),
				# Run("echo server 10.10.20.1 iburst >> /etc/ntp.conf"),
				# Run("service ntp restart")
				Push(localpaths=["ntp_client.conf"], remotepath="/etc/"),
				Run("mv /etc/ntp_client.conf ntp.conf"),
				Run("service ntp restart")
			],
			required = requirement,
			scheduler = scheduler
	)

	sleep(ntp)

	requirement = (ntp01, ntp02)

elif ntp == 0:
	ntp01 = SshJob(
			node = server,
			commands = [
				# Run("sed -i -e s/'broadcast 10.10.20.255'//g /etc/ntp.conf"),
				# Run("sed -i -e s/'listen on data'//g /etc/ntp.conf"),
				Run("service ntp stop")
			],
			required = requirement,
			scheduler = scheduler
	)

	ntp02 = SshJob(
			node = client,
			commands = [
				# Run("sed -i -e s/'disable auth'//g /etc/ntp.conf"),
				# Run("sed -i -e s/broadcastclient//g /etc/ntp.conf"),
				# Run("sed -i -e s/'server 10.10.20.1 iburst'//g /etc/ntp.conf"),
				Run("service ntp stop")
			],
			required = requirement,
			scheduler = scheduler
	)

	requirement = (ntp01, ntp02)


# launching probes

if run is not None:
	tcpdump01 = SshJob(
			node = server,
			commands = [
				Run("pkill tcpdump || true"),
				Run("nohup tcpdump -i %s -s 48 -w tests/left.pcap > /dev/null 2>&1 < /dev/null & sleep 5" % IFACE)
			],
			required = requirement,
			scheduler = scheduler
	)

	tcpdump02 = SshJob(
			node = client,
			commands = [
				Run("pkill tcpdump || true"),
				Run("nohup tcpdump -i %s -s 48 -w tests/right.pcap > /dev/null 2>&1 < /dev/null & sleep 5" % IFACE)
			],
			required = requirement,
			scheduler = scheduler
	)

	# ping

	# if run == "default":
	# 	ping = SshJob (
	# 			node = server,
	# 			commands = [
	# 				Run("sleep 5"),
	# 				Run("ping %s -c %i -i 0.001 > tests/pings" % (CLIENTADD, N))
	# 			],
	# 			required = (tcpdump01, tcpdump02),
	# 			scheduler = scheduler
	# 	)

	# elif run == "sizes":
	ping = SshJob (
			node = server,
			commands = [
				Run("sleep 5"),
				Run("for s in %s; do ping %s -c %s -i 0.001 -s $s > tests/pings_$s; sleep 1; done" % (RANGE_, CLIENTADD, N))
			],
			required = (tcpdump01, tcpdump02),
			scheduler = scheduler
	)

	# downloading files

	# download = SshJob (
	# 		node = gateway,
	# 		commands = [
	# 			Run("scp root@%s:tests/* tmp/" % SERVER),
	# 			Run("scp root@%s:tests/* tmp/" % CLIENT),
	# 			Pull(remotepaths=['tmp/'], localpath=PATH, recurse=True)
	# 		],
	# 		required = ping,
	# 		scheduler = scheduler
	# )

	download01 = SshJob (
			node = server,
			commands = [
				Run("pkill tcpdump || true"),
				Pull(remotepaths=['tests/'], localpath=PATH, recurse=True)
			],
			required = ping,
			scheduler = scheduler
	)

	download01 = SshJob (
			node = client,
			commands = [
				Run("pkill tcpdump || true"),
				Pull(remotepaths=['tests/'], localpath=PATH, recurse=True)
			],
			required = ping,
			scheduler = scheduler
	)

# begin

ok = scheduler.orchestrate()

print("orchestrate -", ok)

# analyse

def get_rtts(filename):
	parser = pingparsing.PingParsing()

	rtts = []

	with open(filename, 'r') as file:
		raw = file.read()
		stats = parser.parse(raw)

	for reply in stats.icmp_replies:
		rtt = reply['time']
		rtts.append(rtt)

	return rtts

# def get_owds(inp, outp):
# 	packets_in = np.recfromcsv(inp, delimiter=',', names=['no', 'time', 'len', 'seq'])
# 	packets_out = np.recfromcsv(outp, delimiter=',', names=['no', 'time', 'len', 'seq'])

# 	base = 0
# 	ts_in = {}
# 	for no, time, len, seq in packets_in:
# 		if seq and seq >= 0:
# 			ts_in[seq + base] = time
# 			if seq == 65535:
# 				base += 65536

# 	base = 0
# 	owds = []
# 	for no, time, len, seq in packets_out:
# 		if seq and seq >= 0:
# 			if seq + base in ts_in.keys():
# 				owd = (ts_in[seq + base] - time) * 1000
# 				owds.append(owd)
# 			if seq == 65535:
# 				base += 65536

# 	return owds

def get_owds(leftp, rightp, lefta, righta, size=98):
	packets_left = np.recfromcsv(leftp, delimiter=',', names=['no', 'time', 'len', 'src', 'dst', 'id'])
	packets_right = np.recfromcsv(rightp, delimiter=',', names=['no', 'time', 'len', 'src', 'dst', 'id'])

	reqs_left = {id: [] for id in range(2**16)}
	reps_right = {id: [] for id in range(2**16)}

	for no, time, len, src, dst, id in packets_left:
		src, dst = src.decode(), dst.decode()
		if id and id > 0:
			if src == lefta and dst == righta and len == size:
				reqs_left[id].append(time)

	for no, time, len, src, dst, id in packets_right:
		src, dst = src.decode(), dst.decode()
		if id and id > 0:
			if src == lefta and dst == righta and len == size:
				reps_right[id].append(time)

	owds = []

	for id in range(2**16):
		for i in range(length(reqs_left[id])):
			owd = reps_right[id][i] - reqs_left[id][i]
			owds.append(owd)

	return owds

def get_rtds(leftp, rightp, lefta, righta, size=98):
	def sort_dic(dic):
		keys = sorted(dic)
		new_dic = {key: dic[key] for key in keys}
		return new_dic

	def binary_search(arr, x):
		# if len(arr) == 1:
		# 	return arr[0]

		# else:
		i = 0
		j = length(arr) - 1
		k1 = (i + j) // 2
		k2 = k1 + 1

		while j - i > 0:
			if x < arr[k1] and x < arr[k2]:
				j = k1
				k1 = (i + j) // 2
				k2 = k1 + 1
			elif x > arr[k1] and x > arr[k2]:
				i = k2
				k1 = (i + j) // 2
				k2 = k1 + 1
			else:
				if x - arr[k1] <= arr[k2] - x:
					return arr[k1]
				else:
					return arr[k2]

		return arr[i]


	def closest(dic, x):
		keys = list(dic.keys())
		key = binary_search(keys, x)
		return dic[key]

	packets_left = np.recfromcsv(leftp, delimiter=',', names=['no', 'time', 'len', 'src', 'dst', 'id'])
	packets_right = np.recfromcsv(rightp, delimiter=',', names=['no', 'time', 'len', 'src', 'dst', 'id'])

	reqs_left = {id: [] for id in range(2**16)}
	reqs_right = {id: [] for id in range(2**16)}
	reps_left = {id: [] for id in range(2**16)}
	reps_right = {id: [] for id in range(2**16)}

	for no, time, len, src, dst, id in packets_left:
		src, dst = src.decode(), dst.decode()
		if id and id > 0:
			if src == lefta and dst == righta and len == size:
				reqs_left[id].append(time)
			elif src == righta and dst == lefta and len == size:
				reps_left[id].append(time)

	for no, time, len, src, dst, id in packets_right:
		src, dst = src.decode(), dst.decode()
		if id and id > 0:
			if src == righta and dst == lefta and len == size:
				reqs_right[id].append(time)
			elif src == lefta and dst == righta and len == size:
				reps_right[id].append(time)

	owds_left = {}
	owds_right = {}

	for id in range(2**16):
		for i in range(length(reqs_left[id])):
			owd = reps_right[id][i] - reqs_left[id][i]
			owds_left[reqs_left[id][i]] = owd

		for i in range(length(reps_left[id])):
			owd = reps_left[id][i] - reqs_right[id][i]
			owds_right[reps_left[id][i]] = owd

	owds_left = sort_dic(owds_left)
	owds_right = sort_dic(owds_right)

	rtds = []

	for ts1 in owds_left:
		owd1 = owds_left[ts1]
		owd2 = closest(owds_right, ts1)
		rtd = (owd2 + owd1) * 1000
		rtds.append(rtd)

	return rtds

def clean_extremes(data, percinf=5, percsup=95):
	inf = np.percentile(data, percinf)
	sup = np.percentile(data, percsup)
	new_data = [datum for datum in data if datum >= inf and datum <= sup]
	return new_data

print(ok, analyse)
if ok and analyse:
	os.system("tshark -r %s/left.pcap -T fields -E separator=, -e frame.number -e _ws.col.Time -e frame.len -e ip.src -e ip.dst -e ip.id > %s/left.csv" % (PATH, PATH))
	os.system("tshark -r %s/right.pcap -T fields -E separator=, -e frame.number -e _ws.col.Time -e frame.len -e ip.src -e ip.dst -e ip.id > %s/right.csv" % (PATH, PATH))

	ss_rtts = []
	ss_rtds = []
	ss_owds = []
	rtts = []
	rtds = []
	owds = []
	mus_rtts = []
	mus_owds = []
	mus_rtds = []
	sigs_rtts = []
	sigs_owds = []
	sigs_rtds = []

	for size in RANGE:
		s = size - 42
		rtts_ = get_rtts("%s/pings_%s" % (PATH, s))
		rtts.extend(rtts_)
		ss_rtts.extend(length(rtts_) * [size])
		mus_rtts.append(np.mean(rtts_))
		sigs_rtts.append(np.std(rtts_))

		leftp = "%s/left.csv" % PATH
		rightp = "%s/right.csv" % PATH
		lefta = SERVERADD
		righta = CLIENTADD

		owds_ = get_owds(leftp, rightp, lefta, righta)
		owds.extend(owds_)
		ss_owds.extend(length(owds_) * [size])
		mus_owds.append(np.mean(owds_))
		sigs_owds.append(np.std(owds_))

		rtds_ = get_rtds(leftp, rightp, lefta, righta)
		rtds.extend(rtds_)
		ss_rtds.extend(length(rtds_) * [size])
		mus_rtds.append(np.mean(rtds_))
		sigs_rtds.append(np.std(rtds_))


	fig, axs = plt.subplots(3, 1)

	if run == "default":
		axs[0].scatter(range(len(rtts)), rtts, 1)
		axs[0].set_title("Ping RTT (ms)")

		axs[1].scatter(range(len(owds)), owds, 1)
		axs[1].set_title("Measured OWD (ms)")

		axs[2].scatter(range(len(rtds)), rtds, 1)
		axs[2].set_title("Measured RTD (ms)")

	elif run == "sizes":
		axs[0].scatter(ss_rtts, rtts, 1)
		axs[0].plot([], [])
		axs[0].errorbar(RANGE, mus_rtts, yerr=sigs_rtts)

		axs[1].scatter(ss_owds, owds, 1)
		axs[1].plot([], [])
		axs[1].errorbar(RANGE, mus_owds, yerr=sigs_owds)

		axs[2].scatter(ss_rtds, rtds, 1)
		axs[2].plot([], [])
		axs[2].errorbar(RANGE, mus_rtds, yerr=sigs_rtds)

	plt.show()