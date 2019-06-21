import sys
import os
import time
import daemon

import socket
from .timer import shutdown_timer
from .udp import udp_receiver

from pathlib import Path
import logging

def makeDirIfDoesntExist(dirpath):
    try:
        # Create target Directory
        os.mkdir(dirpath)
        print("Directory " , dirpath ,  " Created ") 
    except FileExistsError:
        print("Directory " , dirpath ,  " already exists")

class PowMonManClient:

    port_number = 7444
    udp_port_number = port_number-1
    server_ip = [];
    timer = shutdown_timer()
    shutdown_time = 10 #600 
    poll_rate = 5
    
    def __init__(self):
        pass
    
    def listenForServer(self):
        self.logger.info("Listening for PowMonMan server...")
        packets_received = 0
        with udp_receiver(self.udp_port_number) as ur:
            for (address,data) in ur:
                address = address[0] # chop off port number
                if data == "PowMonMan Server!":
                    self.logger.info("Found! ({})".format(address))
                    return address
                else:
                    continue
                    
                packets_received+=1
                
                if packets_received>10:
                    self.logger.info("")
                    self.logger.info("Receiving packets, however they're not what I expect...\n" + 
                          "Guessing that the server address is {}\n".format(address) +
                          "however this may be incorrect.  Double check server configuration\n" +
                          "if PowMonMan is not functioning correctly.\n")
                    return address
        return []

    def checkPowerState(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except Exception as e:
            self.logger.info("Failed to create socket")
            sys.exit()
            
        try:
            s.connect((self.server_ip,self.port_number))
            data = s.recv(4096)
            return(data.decode("utf-8"))
        except:
            self.logger.info("Unable to connect to server.")
            return("error connecting")

    def sendShutdownSignal(self):
        self.logger.info("SHUTDOWN INITIATED")
        
        if sys.platform in ["darwin","linux"]:
            cmd = "sudo shutdown -h now"
        if sys.platform in ["win32"]:
            cmd = "shutdown /s"

        from subprocess import call        
        call(cmd.split())
        sys.exit(0);

    def run(self):

        self.logger.info("Starting PowMonMan_Client...")
        self.server_ip = self.listenForServer()              
        if not self.server_ip:
            self.logger.info("Could not find a server on the network!")
        else:
            self.logger.info("    Server found at:      {}\n".format(self.server_ip) + 
                  "    Using port:           {}\n".format(self.port_number) + 
                  "    Shutdown time (sec):  {}\n".format(self.shutdown_time) + 
                  "    Current power status: {}".format(self.checkPowerState()))
            
        power_state      = "on"
        prev_power_state = "on"

        while True:
            
            power_state = self.checkPowerState()
            self.logger.info(power_state)
            
            if (power_state != prev_power_state) and (power_state=="on"):
                self.poll_rate = 5
                self.timer.stop()
            elif (power_state != prev_power_state) and (power_state=="off"):
                self.poll_rate = 1
                self.timer.start()
            elif (power_state == prev_power_state) and (power_state=="off"):
                elapsed = self.timer.get_elapsed()
                if elapsed > self.shutdown_time:
                    self.sendShutdownSignal()
                else:
                    self.logger.info("{} seconds until shutdown!".format(round(self.shutdown_time - elapsed)))

            prev_power_state = power_state
            time.sleep(self.poll_rate)

    def startLogging(self):
        logdir_path = '/var/log/PowMonMan/'
        logfile_path = '/var/log/PowMonMan/client.log'

        makeDirIfDoesntExist(logdir_path)
        
        if not os.path.isfile(logfile_path):
            try:
                Path(logfile_path).touch()
            except Exception as e:
                print("Could not open logfile. Are you running with root permissions?")

        self.logger = logging.getLogger('client')
        hdlr = logging.FileHandler(logfile_path)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        self.logger.addHandler(hdlr)
        self.logger.setLevel(logging.INFO)            

def main():
    with daemon.DaemonContext(stdout = sys.stdout, stderr = sys.stderr):
        P = PowMonManClient();
        P.startLogging()        
        P.run()

if __name__=="__main__":
    main()