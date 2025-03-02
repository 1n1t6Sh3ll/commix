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

import re
import os
import sys
from src.utils import menu
from src.utils import logs
from src.utils import settings
from src.utils import session_handler
from src.core.requests import headers
from src.core.requests import requests
from src.core.requests import parameters
from src.core.modules import modules_handler
from src.core.requests import authentication
from src.core.injections.controller import checks
from src.thirdparty.six.moves import input as _input
from src.thirdparty.six.moves import urllib as _urllib
from src.thirdparty.colorama import Fore, Back, Style, init
from src.core.injections.blind.techniques.time_based import tb_handler
from src.core.injections.semiblind.techniques.file_based import fb_handler
from src.core.injections.results_based.techniques.classic import cb_handler
from src.core.injections.results_based.techniques.eval_based import eb_handler

"""
Command Injection and exploitation controller.
Checks if the testable parameter is exploitable.
"""

"""
Check for previously stored sessions.
"""
def check_for_stored_sessions(url, http_request_method):

  if not menu.options.ignore_session:
    if os.path.isfile(settings.SESSION_FILE) and not settings.REQUIRED_AUTHENTICATION:
      if not menu.options.tech:
        settings.SESSION_APPLIED_TECHNIQUES = session_handler.applied_techniques(url, http_request_method)
        menu.options.tech = settings.SESSION_APPLIED_TECHNIQUES
      if session_handler.check_stored_parameter(url, http_request_method):
        settings.LOAD_SESSION = True
        return True    
        
"""
Check for previously stored injection level.
"""
def check_for_stored_levels(url, http_request_method):

  if not menu.options.ignore_session:
    if menu.options.level == settings.DEFAULT_INJECTION_LEVEL:
      menu.options.level = session_handler.applied_levels(url, http_request_method)
      if type(menu.options.level) is not int :
        menu.options.level = settings.DEFAULT_INJECTION_LEVEL
        
"""
Basic heuristic checks for code injection warnings
"""
def heuristic_basic(url, http_request_method):
  injection_type = "results-based dynamic code evaluation"
  technique = "dynamic code evaluation technique"
  technique = "(" + injection_type.split(" ")[0] + ") " + technique + ""

  if menu.options.skip_heuristics:
    if settings.VERBOSITY_LEVEL != 0:   
      debug_msg = "Skipping (basic) heuristic detection for " + technique + "."
      print(settings.print_debug_msg(debug_msg))
    return url
  else:
    settings.EVAL_BASED_STATE = True
    try:
      try:
        if re.findall(r"=(.*)&", url):
          url = url.replace("/&", "/e&")
        elif re.findall(r"=(.*)&", menu.options.data):
          menu.options.data = menu.options.data.replace("/&", "/e&")
      except TypeError as err_msg:
        pass
      if not settings.IDENTIFIED_WARNINGS and not settings.IDENTIFIED_PHPINFO:  
        if settings.VERBOSITY_LEVEL != 0:   
          debug_msg = "Starting (basic) heuristic detection for " + technique + "."
          print(settings.print_debug_msg(debug_msg))
        for payload in settings.PHPINFO_CHECK_PAYLOADS:
          payload = checks.perform_payload_modification(payload)
          if settings.VERBOSITY_LEVEL >= 1:
            print(settings.print_payload(payload))
          if not menu.options.data:
            request = _urllib.request.Request(url.replace(settings.INJECT_TAG, payload))
          else:
            data = menu.options.data.replace(settings.INJECT_TAG, payload)
            request = _urllib.request.Request(url, data.encode(settings.DEFAULT_CODEC))
          headers.do_check(request)
          response = requests.get_request_response(request)
          if type(response) is not bool:
            html_data = checks.page_encoding(response, action="decode")
            match = re.search(settings.CODE_INJECTION_PHPINFO, html_data)
            if match:
              technique = technique + " (possible PHP version: '" + match.group(1) + "')"
              settings.IDENTIFIED_PHPINFO = True
            else:
              for warning in settings.CODE_INJECTION_WARNINGS:
                if warning in html_data:
                  settings.IDENTIFIED_WARNINGS = True
                  break
            if settings.IDENTIFIED_WARNINGS or settings.IDENTIFIED_PHPINFO:
              info_msg = "Heuristic detection shows that target might be injectable via " + technique + "." 
              print(settings.print_bold_info_msg(info_msg))
              break

      settings.EVAL_BASED_STATE = False
      return url

    except (_urllib.error.URLError, _urllib.error.HTTPError) as err_msg:
      print(settings.print_critical_msg(err_msg))
      raise SystemExit()

# Check if it's exploitable via classic command injection technique.
def classic_command_injection_technique(url, timesec, filename, http_request_method):
  injection_type = "results-based OS command injection"
  technique = "classic command injection technique"
  if not settings.SKIP_COMMAND_INJECTIONS:
    if (len(menu.options.tech) == 0 or "c" in menu.options.tech):
      settings.CLASSIC_STATE = None
      if cb_handler.exploitation(url, timesec, filename, http_request_method, injection_type, technique) != False:
        if (len(menu.options.tech) == 0 or "e" in menu.options.tech):
          while True:
            if not menu.options.batch:
              settings.CLASSIC_STATE = True
              question_msg = "Skipping of code injection tests is recommended. "
              question_msg += "Do you agree? [Y/n] > "
              procced_option = _input(settings.print_question_msg(question_msg))
            else:
              procced_option = ""
            if len(procced_option) == 0:
               procced_option = "Y"
            if procced_option in settings.CHOICE_YES:
              settings.SKIP_CODE_INJECTIONS = True
              break
            elif procced_option in settings.CHOICE_NO:
              break
            elif procced_option in settings.CHOICE_QUIT:
              raise SystemExit()
            else:
              err_msg = "'" + procced_option + "' is not a valid answer."  
              print(settings.print_error_msg(err_msg))
              pass
      else:
        settings.CLASSIC_STATE = False
    else:
      if settings.VERBOSITY_LEVEL != 0:   
        debug_msg = "Skipping test the " + "(" + injection_type.split(" ")[0] + ") " + technique + ". "
        print(settings.print_debug_msg(debug_msg))

# Check if it's exploitable via dynamic code evaluation technique.   
def dynamic_code_evaluation_technique(url, timesec, filename, http_request_method):
  injection_type = "results-based dynamic code evaluation"
  technique = "dynamic code evaluation technique"
  if not settings.SKIP_CODE_INJECTIONS:
    if (len(menu.options.tech) == 0 or "e" in menu.options.tech) or settings.SKIP_COMMAND_INJECTIONS:
      settings.EVAL_BASED_STATE = None
      if eb_handler.exploitation(url, timesec, filename, http_request_method, injection_type, technique) != False:
        while True:
          if not menu.options.batch:
            settings.EVAL_BASED_STATE = True
            question_msg = "Skipping of further command injection checks is recommended. "
            question_msg += "Do you agree? [Y/n] > "
            procced_option = _input(settings.print_question_msg(question_msg))
          else:
            procced_option = ""
          if len(procced_option) == 0:
             procced_option = "Y"
          if procced_option in settings.CHOICE_YES:
            settings.SKIP_COMMAND_INJECTIONS = True
            break
          elif procced_option in settings.CHOICE_NO:
            if settings.SKIP_COMMAND_INJECTIONS:
              settings.SKIP_COMMAND_INJECTIONS = False
            break
          elif procced_option in settings.CHOICE_QUIT:
            raise SystemExit()
          else:
            err_msg = "'" + procced_option + "' is not a valid answer."  
            print(settings.print_error_msg(err_msg))
            pass
      else:
        settings.EVAL_BASED_STATE = False
    else:
      if settings.VERBOSITY_LEVEL != 0:   
        debug_msg = "Skipping test the " + "(" + injection_type.split(" ")[0] + ") " + technique + ". "
        print(settings.print_debug_msg(debug_msg))
  else:
    if settings.VERBOSITY_LEVEL != 0:   
      debug_msg = "Skipping test the " + "(" + injection_type.split(" ")[0] + ") " + technique + ". "
      print(settings.print_debug_msg(debug_msg))


# Check if it's exploitable via time-based command injection technique.
def timebased_command_injection_technique(url, timesec, filename, http_request_method, url_time_response):
  injection_type = "blind OS command injection"
  technique = "time-based command injection technique"
  if not settings.SKIP_COMMAND_INJECTIONS:
    if (len(menu.options.tech) == 0 or "t" in menu.options.tech):
      settings.TIME_BASED_STATE = None
      if tb_handler.exploitation(url, timesec, filename, http_request_method, url_time_response, injection_type, technique) != False:
        settings.TIME_BASED_STATE = True
      else:
        settings.TIME_BASED_STATE = False
    else:
      if settings.VERBOSITY_LEVEL != 0:   
        debug_msg = "Skipping test the " + "(" + injection_type.split(" ")[0] + ") " + technique + ". "
        print(settings.print_debug_msg(debug_msg))

# Check if it's exploitable via file-based command injection technique.
def filebased_command_injection_technique(url, timesec, filename, http_request_method, url_time_response):
  injection_type = "semi-blind command injection"
  technique = "file-based command injection technique"
  if not settings.SKIP_COMMAND_INJECTIONS:
    if (len(menu.options.tech) == 0 or "f" in menu.options.tech):
      settings.FILE_BASED_STATE = None
      if fb_handler.exploitation(url, timesec, filename, http_request_method, url_time_response, injection_type, technique) != False:
        settings.FILE_BASED_STATE = True
      else:
        settings.FILE_BASED_STATE = False
    else:
      if settings.VERBOSITY_LEVEL != 0:   
        debug_msg = "Skipping test the " + "(" + injection_type.split(" ")[0] + ") " + technique + ". "
        print(settings.print_debug_msg(debug_msg))

"""
Proceed to the injection process for the appropriate parameter.
"""
def injection_proccess(url, check_parameter, http_request_method, filename, timesec):

  if menu.options.ignore_code: 
    info_msg = "Ignoring '" + str(menu.options.ignore_code) + "' HTTP error code. "
    print(settings.print_info_msg(info_msg))

  # Skipping specific injection techniques.
  if settings.SKIP_TECHNIQUES:
    menu.options.tech = "".join(settings.AVAILABLE_TECHNIQUES)
    for skip_tech_name in settings.AVAILABLE_TECHNIQUES:
      if skip_tech_name in menu.options.skip_tech:
        menu.options.tech = menu.options.tech.replace(skip_tech_name,"")
    if len(menu.options.tech) == 0:
      err_msg = "Detection procedure was aborted due to skipping all injection techniques."
      print(settings.print_critical_msg(err_msg))
      raise SystemExit

  # User-Agent HTTP header / Referer HTTP header / 
  # Host HTTP header / Custom HTTP header Injection(s)
  if check_parameter.startswith(" "):
    header_name = ""
    the_type = " HTTP header"
  else:
    if settings.COOKIE_INJECTION: 
      header_name = " cookie"
    else:
      header_name = ""
    the_type = " parameter"
    check_parameter = " '" + check_parameter + "'"

  # Estimating the response time (in seconds)
  timesec, url_time_response = requests.estimate_response_time(url, timesec)
  # Load modules
  modules_handler.load_modules(url, http_request_method, filename)

  if not settings.LOAD_SESSION:
    if (len(menu.options.tech) == 0 or "e" in menu.options.tech):
      # Check for identified warnings
      url = heuristic_basic(url, http_request_method)
      if settings.IDENTIFIED_WARNINGS or settings.IDENTIFIED_PHPINFO:
        while True:
          if not menu.options.batch:
            question_msg = "Skipping of further command injection tests is recommended. "
            question_msg += "Do you agree? [Y/n] > "
            procced_option = _input(settings.print_question_msg(question_msg))
          else:
            procced_option = ""
          if procced_option in settings.CHOICE_YES or len(procced_option) == 0:
            settings.CLASSIC_STATE = settings.TIME_BASED_STATE = settings.FILE_BASED_STATE = False
            settings.EVAL_BASED_STATE = settings.SKIP_COMMAND_INJECTIONS = True
            break
          elif procced_option in settings.CHOICE_NO:
            break
          elif procced_option in settings.CHOICE_QUIT:
            raise SystemExit()
          else:
            err_msg = "'" + procced_option + "' is not a valid answer."  
            print(settings.print_error_msg(err_msg))
            pass

    info_msg = "Setting the" 
    if not header_name == " cookie" and not the_type == " HTTP header":
      info_msg += " " + str(http_request_method) + ""
    info_msg += ('', ' (JSON)')[settings.IS_JSON] + ('', ' (SOAP/XML)')[settings.IS_XML] 
    if header_name == " cookie" :
      info_msg += str(header_name) + str(the_type) + str(check_parameter) + " for tests."
    else:
      info_msg += str(the_type) + str(header_name) + str(check_parameter) + " for tests."
    print(settings.print_info_msg(info_msg))

  if menu.options.failed_tries and \
     menu.options.tech and not "f" in menu.options.tech and not \
     menu.options.failed_tries:
    warn_msg = "Due to the provided (unsuitable) injection technique" 
    warn_msg += "s"[len(menu.options.tech) == 1:][::-1] + ", "
    warn_msg += "the option '--failed-tries' will be ignored."
    print(settings.print_warning_msg(warn_msg) + Style.RESET_ALL)

  # Procced with file-based semiblind command injection technique,
  # once the user provides the path of web server's root directory.
  if menu.options.web_root and \
     menu.options.tech and not "f" in menu.options.tech:
      if not menu.options.web_root.endswith("/"):
         menu.options.web_root =  menu.options.web_root + "/"
      if checks.procced_with_file_based_technique():
        menu.options.tech = "f"

  if settings.SKIP_COMMAND_INJECTIONS:
    dynamic_code_evaluation_technique(url, timesec, filename, http_request_method)
    classic_command_injection_technique(url, timesec, filename, http_request_method)
  else:
    classic_command_injection_technique(url, timesec, filename, http_request_method)
    dynamic_code_evaluation_technique(url, timesec, filename, http_request_method)
  timebased_command_injection_technique(url, timesec, filename, http_request_method, url_time_response)
  filebased_command_injection_technique(url, timesec, filename, http_request_method, url_time_response)

  # All injection techniques seems to be failed!
  if settings.CLASSIC_STATE == settings.EVAL_BASED_STATE == settings.TIME_BASED_STATE == settings.FILE_BASED_STATE == False :
    warn_msg = "The tested"
    if header_name != " cookie" and the_type != " HTTP header":
      warn_msg += " " + str(http_request_method) + ""
    warn_msg += str(the_type) + str(header_name) + str(check_parameter)
    warn_msg += " seems to be not injectable."
    print(settings.print_warning_msg(warn_msg))

"""
Inject HTTP headers (User-agent / Referer / Host) (if level > 2).
"""
def http_headers_injection(url, http_request_method, filename, timesec):
  # Disable Cookie Injection 
  settings.COOKIE_INJECTION = False

  def user_agent_injection(url, http_request_method, filename, timesec): 
    user_agent = menu.options.agent
    if not menu.options.shellshock:
      menu.options.agent = settings.INJECT_TAG
    settings.USER_AGENT_INJECTION = True
    if settings.USER_AGENT_INJECTION:
      check_parameter = header_name = " User-Agent"
      settings.HTTP_HEADER = header_name[1:].replace("-","").lower()
      check_for_stored_sessions(url, http_request_method)
      injection_proccess(url, check_parameter, http_request_method, filename, timesec)
    settings.USER_AGENT_INJECTION = False
    menu.options.agent = user_agent

  def referer_injection(url, http_request_method, filename, timesec):
    referer = menu.options.referer
    if not menu.options.shellshock:
      menu.options.referer = settings.INJECT_TAG
    settings.REFERER_INJECTION = True
    if settings.REFERER_INJECTION:
      check_parameter =  header_name = " Referer"
      settings.HTTP_HEADER = header_name[1:].lower()
      check_for_stored_sessions(url, http_request_method)
      injection_proccess(url, check_parameter, http_request_method, filename, timesec)
    settings.REFERER_INJECTION = False 
    menu.options.agent = referer

  def host_injection(url, http_request_method, filename, timesec):
    if not menu.options.shellshock:
      menu.options.host = settings.INJECT_TAG
    settings.HOST_INJECTION = True
    if settings.HOST_INJECTION:
      check_parameter =  header_name = " Host"
      settings.HTTP_HEADER = header_name[1:].lower()
      check_for_stored_sessions(url, http_request_method)
      injection_proccess(url, check_parameter, http_request_method, filename, timesec)
      settings.HOST_INJECTION = False 

  # User-Agent HTTP header injection
  if menu.options.skip_parameter == None:
    if menu.options.test_parameter == None or "user-agent" in menu.options.test_parameter.lower():
      user_agent_injection(url, http_request_method, filename, timesec)
  else:
    if "user-agent" not in menu.options.skip_parameter.lower():
      user_agent_injection(url, http_request_method, filename, timesec)  

  # Referer HTTP header injection
  if menu.options.skip_parameter == None:
    if menu.options.test_parameter == None or "referer" in menu.options.test_parameter.lower():
      referer_injection(url, http_request_method, filename, timesec)
  else:
    if "referer" not in menu.options.skip_parameter.lower():
      referer_injection(url, http_request_method, filename, timesec)   

  # Host HTTP header injection
  if menu.options.skip_parameter == None:
    if menu.options.test_parameter == None or "host" in menu.options.test_parameter.lower():
      host_injection(url, http_request_method, filename, timesec)
  else:
    if "host" not in menu.options.skip_parameter.lower():
      host_injection(url, http_request_method, filename, timesec)   

"""
Check for stored injections on User-agent / Referer headers (if level > 2).
"""
def stored_http_header_injection(url, check_parameter, http_request_method, filename, timesec):

  for check_parameter in settings.HTTP_HEADERS:
    settings.HTTP_HEADER = check_parameter
    if check_for_stored_sessions(url, http_request_method):
      if check_parameter == "referer":
        menu.options.referer = settings.INJECT_TAG
        settings.REFERER_INJECTION = True
      elif check_parameter == "host":
        menu.options.host= settings.INJECT_TAG
        settings.HOST_INJECTION = True
      else:  
        menu.options.agent = settings.INJECT_TAG
        settings.USER_AGENT_INJECTION = True
      injection_proccess(url, check_parameter, http_request_method, filename, timesec)

  if not settings.LOAD_SESSION:
    http_headers_injection(url, http_request_method, filename, timesec)


"""
Cookie injection 
"""
def cookie_injection(url, http_request_method, filename, timesec):

  settings.COOKIE_INJECTION = True

  # Cookie Injection
  if settings.COOKIE_INJECTION == True:
    cookie_value = menu.options.cookie

    header_name = " cookie"
    settings.HTTP_HEADER = header_name[1:].lower()
    cookie_parameters = parameters.do_cookie_check(menu.options.cookie)
    if type(cookie_parameters) is str:
      cookie_parameters_list = []
      cookie_parameters_list.append(cookie_parameters)
      cookie_parameters = cookie_parameters_list

    # Remove whitespaces 
    cookie_parameters = [x.replace(" ", "") for x in cookie_parameters]

    check_parameters = []
    for i in range(0, len(cookie_parameters)):
      menu.options.cookie = cookie_parameters[i]
      check_parameter = parameters.specify_cookie_parameter(menu.options.cookie)
      check_parameters.append(check_parameter)

    checks.print_non_listed_params(check_parameters, http_request_method, header_name)

    for i in range(0, len(cookie_parameters)):
      parameter = menu.options.cookie = cookie_parameters[i]
      check_parameter = parameters.specify_cookie_parameter(parameter)
      if check_parameter != parameter:
        if len(check_parameter) > 0:
          settings.TESTABLE_PARAMETER = check_parameter

        # Check if testable parameter(s) are provided
        if len(settings.TEST_PARAMETER) > 0:
          if menu.options.test_parameter != None:
            param_counter = 0
            for check_parameter in check_parameters:
              if check_parameter in "".join(settings.TEST_PARAMETER).split(","):
                menu.options.cookie = cookie_parameters[param_counter]
                # Check for session file 
                check_for_stored_sessions(url, http_request_method)
                injection_proccess(url, check_parameter, http_request_method, filename, timesec) 
              param_counter += 1
            break  
        else:
          # Check for session file 
          check_for_stored_sessions(url, http_request_method)
          injection_proccess(url, check_parameter, http_request_method, filename, timesec) 
 
  if settings.COOKIE_INJECTION == True:
    # Restore cookie value
    menu.options.cookie = cookie_value
    # Disable cookie injection 
    settings.COOKIE_INJECTION = False

"""
Check if HTTP Method is GET.
""" 
def get_request(url, http_request_method, filename, timesec):

  #if not settings.COOKIE_INJECTION:
  found_url = parameters.do_GET_check(url, http_request_method)
  if found_url != False:

    check_parameters = []
    for i in range(0, len(found_url)):
      url = found_url[i]
      check_parameter = parameters.vuln_GET_param(url)
      check_parameters.append(check_parameter)

    header_name = ""
    checks.print_non_listed_params(check_parameters, http_request_method, header_name)

    for i in range(0, len(found_url)):
      url = found_url[i]
      check_parameter = parameters.vuln_GET_param(url)
      if check_parameter != url:
        if len(check_parameter) > 0:
          settings.TESTABLE_PARAMETER = check_parameter
          
        # Check if testable parameter(s) are provided
        if len(settings.TESTABLE_PARAMETER) > 0:
          if menu.options.test_parameter != None:
            url_counter = 0
            for check_parameter in check_parameters:
              if check_parameter in "".join(settings.TEST_PARAMETER).split(","):
                url = found_url[url_counter]
                # Check for session file 
                check_for_stored_sessions(url, http_request_method)
                injection_proccess(url, check_parameter, http_request_method, filename, timesec)
              url_counter += 1
            break
          else:
            # Check for session file 
            check_for_stored_sessions(url, http_request_method)
            injection_proccess(url, check_parameter, http_request_method, filename, timesec)
        else:
          # Check for session file 
          check_for_stored_sessions(url, http_request_method)
          injection_proccess(url, check_parameter, http_request_method, filename, timesec)

  # Enable Cookie Injection
  if menu.options.level > settings.DEFAULT_INJECTION_LEVEL and menu.options.cookie:
    settings.COOKIE_INJECTION = True

"""
Check if HTTP Method is POST.
""" 
def post_request(url, http_request_method, filename, timesec):

  # Check if HTTP Method is POST.
  parameter = menu.options.data
  found_parameter = parameters.do_POST_check(parameter, http_request_method)

  # Check if singe entry parameter
  if type(found_parameter) is str:
    found_parameter_list = []
    found_parameter_list.append(found_parameter)
    found_parameter = found_parameter_list

  if settings.IS_XML:
    # Remove junk data
    found_parameter = [x for x in found_parameter if settings.INJECT_TAG in x]
  else:     
    # Remove whitespaces   
    found_parameter = [x.replace(" ", "") for x in found_parameter]

  # Check if multiple parameters
  check_parameters = []
  for i in range(0, len(found_parameter)):
    parameter = menu.options.data = found_parameter[i]
    check_parameter = parameters.vuln_POST_param(parameter, url)
    check_parameters.append(check_parameter)

  header_name = ""
  checks.print_non_listed_params(check_parameters, http_request_method, header_name)

  for i in range(0, len(found_parameter)):
    #if settings.INJECT_TAG in found_parameter[i]:
    parameter = menu.options.data = found_parameter[i]
    check_parameter = parameters.vuln_POST_param(parameter, url)
    if check_parameter != parameter:
      if len(check_parameter) > 0:
        settings.TESTABLE_PARAMETER = check_parameter
      # Check if testable parameter(s) are provided
      if len(settings.TESTABLE_PARAMETER) > 0:
        if menu.options.test_parameter != None:
          param_counter = 0
          for check_parameter in check_parameters:
            if check_parameter in "".join(settings.TEST_PARAMETER).split(","):
              menu.options.data = found_parameter[param_counter]
              check_for_stored_sessions(url, http_request_method)
              injection_proccess(url, check_parameter, http_request_method, filename, timesec)
            param_counter += 1
          break
        else:
          # Check for session file 
          check_for_stored_sessions(url, http_request_method)
          injection_proccess(url, check_parameter, http_request_method, filename, timesec)
      else:
        # Check for session file 
        check_for_stored_sessions(url, http_request_method)
        injection_proccess(url, check_parameter, http_request_method, filename, timesec)

  # Enable Cookie Injection
  if menu.options.level > settings.DEFAULT_INJECTION_LEVEL and menu.options.cookie:
    settings.COOKIE_INJECTION = True

"""
Perform checks
"""
def perform_checks(url, http_request_method, filename):

  def basic_level_checks():
    if not menu.options.bulkfile:
      settings.PERFORM_BASIC_SCANS = False
    else:
      settings.PERFORM_BASIC_SCANS = True
      settings.SKIP_CODE_INJECTIONS = False
      settings.SKIP_COMMAND_INJECTIONS = False
      settings.IDENTIFIED_WARNINGS = False
      settings.IDENTIFIED_PHPINFO = False
    # Check if HTTP Method is GET.
    if not menu.options.data:
      get_request(url, http_request_method, filename, timesec)
    # Check if HTTP Method is POST.      
    else:
      post_request(url, http_request_method, filename, timesec)

  timesec = settings.TIMESEC
  # Check if authentication is needed.
  if menu.options.auth_url and menu.options.auth_data:
    # Do the authentication process.
    authentication.authentication_process()
    try:
      # Check if authentication page is the same with the next (injection) URL
      if _urllib.request.urlopen(url, timeout=settings.TIMEOUT).read() == _urllib.request.urlopen(menu.options.auth_url, timeout=settings.TIMEOUT).read():
        err_msg = "It seems that the authentication procedure has failed."
        print(settings.print_critical_msg(err_msg))
        raise SystemExit()
    except (_urllib.error.URLError, _urllib.error.HTTPError) as err_msg:
      print(settings.print_critical_msg(err_msg))
      raise SystemExit()
  elif menu.options.auth_url or menu.options.auth_data: 
    err_msg = "You must specify both login panel URL and login parameters."
    print(settings.print_critical_msg(err_msg))
    raise SystemExit()
  else:
    pass

  if menu.options.shellshock:
    menu.options.level = settings.HTTP_HEADER_INJECTION_LEVEL
  else:
    check_for_stored_levels(url, http_request_method)

  if settings.PERFORM_BASIC_SCANS:
    basic_level_checks()

  # Check for stored injections on User-agent / Referer / Host HTTP headers (if level > 2).
  if menu.options.level >= settings.HTTP_HEADER_INJECTION_LEVEL:
    if settings.INJECTED_HTTP_HEADER == False :
      check_parameter = ""
      stored_http_header_injection(url, check_parameter, http_request_method, filename, timesec)
  else:
    # Enable Cookie Injection
    if menu.options.level > settings.DEFAULT_INJECTION_LEVEL:
      if menu.options.cookie:
        cookie_injection(url, http_request_method, filename, timesec)
      else:
        warn_msg = "The HTTP Cookie header is not provided, "
        warn_msg += "so this test is going to be skipped."
        print(settings.print_warning_msg(warn_msg))
    else:
      # Custom header Injection
      if settings.CUSTOM_HEADER_INJECTION == True:
        check_parameter =  header_name = " " + settings.CUSTOM_HEADER_NAME
        settings.HTTP_HEADER = header_name[1:].lower()
        check_for_stored_sessions(url, http_request_method)
        injection_proccess(url, check_parameter, http_request_method, filename, timesec)
        settings.CUSTOM_HEADER_INJECTION = None
  

  if settings.INJECTION_CHECKER == False:
    return False
  else:
    return True  

"""
General check on every injection technique.
"""
def do_check(url, http_request_method, filename):
  # Check for '--tor' option.
  if menu.options.tor: 
    if not menu.options.tech or "t" in menu.options.tech or "f" in menu.options.tech:
      warn_msg = "It is highly recommended to avoid usage of switch '--tor' for "
      warn_msg += "time-based injections because of inherent high latency time."
      print(settings.print_warning_msg(warn_msg))

  # Check for "backticks" tamper script.
  if settings.USE_BACKTICKS == True:
    if not menu.options.tech or "e" in menu.options.tech or "t" in menu.options.tech or "f" in menu.options.tech:
      warn_msg = "Commands substitution using backtics is only supported by the (results-based) classic command injection technique. "
      print(settings.print_warning_msg(warn_msg) + Style.RESET_ALL)

  # Check for "wizard" switch.
  if menu.options.wizard:
    if perform_checks(url, http_request_method, filename) == False:
      scan_level = menu.options.level
      while int(scan_level) < int(settings.HTTP_HEADER_INJECTION_LEVEL) and settings.LOAD_SESSION != True:
        while True:
          if not menu.options.batch:
            question_msg = "Do you want to increase to '--level=" + str(scan_level + 1) 
            question_msg += "' in order to perform more tests? [Y/n] > "
            next_level = _input(settings.print_question_msg(question_msg))
          else:
            next_level = ""
          if len(next_level) == 0:
             next_level = "Y"
          if next_level in settings.CHOICE_YES:
            menu.options.level = int(menu.options.level + scan_level)
            if perform_checks(url, http_request_method, filename) == False and scan_level < settings.HTTP_HEADER_INJECTION_LEVEL :
              scan_level = scan_level + 1
            else:
              break  
          elif next_level in settings.CHOICE_NO:
            break
          elif next_level in settings.CHOICE_QUIT:
            raise SystemExit()
          else:
            err_msg = "'" + next_level + "' is not a valid answer."  
            print(settings.print_error_msg(err_msg))
            pass
  else:
    perform_checks(url, http_request_method, filename)
    
  # All injection techniques seems to be failed!
  if settings.CLASSIC_STATE == settings.EVAL_BASED_STATE == settings.TIME_BASED_STATE == settings.FILE_BASED_STATE == False :
    if settings.INJECTION_CHECKER == False and not settings.CHECK_BOTH_OS:
      err_msg = "All tested parameters "
      if menu.options.level > 2:
        err_msg += "and HTTP headers "
      err_msg += "appear to be not injectable."
      if not menu.options.alter_shell :
        err_msg += " Try to use the option '--alter-shell'"
      else:
        err_msg += " Try to remove the option '--alter-shell'"
      if menu.options.level < settings.HTTP_HEADER_INJECTION_LEVEL :
        err_msg += " and/or increase '--level' values to perform"
        err_msg += " more tests (i.e 'User-Agent', 'Referer', 'Host', 'Cookie' etc)"
      if menu.options.skip_empty:
        err_msg += " and/or remove the option '--skip-empty'"  
      err_msg += "."
      print(settings.print_critical_msg(err_msg))

  logs.print_logs_notification(filename, url)
  if not settings.CHECK_BOTH_OS and not menu.options.bulkfile:
    # if not menu.options.bulkfile or settings.EOF:
    #   print(settings.SINGLE_WHITESPACE)
    raise SystemExit()
# eof