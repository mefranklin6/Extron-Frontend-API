import urllib.error
import urllib.request
from datetime import datetime

from extronlib.system import Ping, ProgramLog, SetAutomaticTime

sys_allowed_flag = True
try:
    import sys
    import traceback
except:
    sys_allowed_flag = False

from extronlib.system import File, SaveProgramLog, Timer


def log(message, level="info"):
    """
    Logs a message with a given severity level.

    Parameters:
    message (str): The message to log.
    level (str): The severity level of the log. Options are: info, warning, error.
    """

    # Log internally and allow for future log forwarding
    ProgramLog(str(message), level)


def set_ntp(ntp_primary, ntp_secondary=None):
    try:
        success_count, fail_count, rtt = Ping(ntp_primary, count=1)
        if success_count > 0:
            SetAutomaticTime(ntp_primary)
            log("Set NTP to primary server at {}".format(ntp_primary), "info")
            log("NTP Primary RTT: {}".format(rtt), "info")
            return
        if ntp_secondary:
            success_count, fail_count, rtt = Ping(ntp_secondary, count=1)
            if success_count > 0:
                SetAutomaticTime(ntp_secondary)
                log("Set NTP to secondary server at {}".format(ntp_secondary), "info")
                return
            else:
                log("NTP servers are unreachable", "error")
    except Exception as e:
        log("Error setting NTP: {}".format(str(e)), "error")


def backend_server_ok(ip):
    headers = {"Content-Type": "application/json"}
    url = "{}/api/v1/{}".format(ip, "test")

    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            response_data = response.read().decode()
            log("Test Response: {}".format(response_data), "info")
            if "OK" in response_data:
                log("Backend server {} is OK".format(str(ip)), "info")
                return True
            else:
                log(
                    "Backend server unknown response: {}".format(str(response_data)),
                    "error",
                )

    # Timeout
    except urllib.error.URLError as e:
        if isinstance(e.reason, urllib.error.URLError) and "timed out" in str(e.reason):
            log("Backend server {} timed out".format(str(ip)), "error")
        else:
            log("URLError: {}".format(str(e)), "error")

    except Exception as e:
        log(str(e), "error")

    return False


class ProgramLogSaver:
    """
    The ProgramLogSaver class is part of:
    "Various Custom tools and debug tool executable",
    origionally written by Jean-Luc Rioux, used under MIT license.

    The class has been slightly modified to work within
    the Extron-Frontend-API project.

    Original sources:
    https://forum.extron.com/showthread.php?t=775
    https://drive.google.com/drive/folders/166frczZjKb0sCiJ--VUMTMOUvWjvpuCZ?usp=sharing

    ----

    This class creates one log file per boot,
    and updates that particular log file whenever the program log changes.
    (checks for changes every 1 minute)
    The check runs in its own thread,
    so errors elsewhere in the program should not interfere with this logging.

    """

    if not File.Exists("/ProgramLogs/"):
        File.MakeDir("/ProgramLogs/")
    __now = datetime.now()
    __nowstr = __now.strftime("%Y-%m-%d-%H-%M-%S")
    __filename = "/ProgramLogs/{}-{}.log".format("ProgramLog", __nowstr)
    __cur_log = ""

    def __readdummyprogramlog():
        f = None
        log = None
        try:
            f = File("/ProgramLogs/temp.log", "r")
        except Exception as e:
            if sys_allowed_flag:
                err_msg = "EXCEPTION:{}:{}:{}".format(
                    __class__.__name__,
                    sys._getframe().f_code.co_name,
                    traceback.format_exc(),
                )
            else:
                err_msg = "EXCEPTION:{}:{}:{}".format(
                    __class__.__name__, "__readdummyprogramlog", e
                )
            log(err_msg, "error")
        if f:
            try:
                log = f.read()
            except Exception as e:
                if sys_allowed_flag:
                    err_msg = "EXCEPTION:{}:{}:{}".format(
                        __class__.__name__,
                        sys._getframe().f_code.co_name,
                        traceback.format_exc(),
                    )
                else:
                    err_msg = "EXCEPTION:{}:{}:{}".format(
                        __class__.__name__, "__readdummyprogramlog", e
                    )
                log(err_msg, "error")
            f.close()
        return log

    def __saveprogramlog():
        try:
            with File(ProgramLogSaver.__filename, "w") as f:
                SaveProgramLog(f)
        except Exception as e:
            if sys_allowed_flag:
                err_msg = "EXCEPTION:{}:{}:{}".format(
                    __class__.__name__,
                    sys._getframe().f_code.co_name,
                    traceback.format_exc(),
                )
            else:
                err_msg = "EXCEPTION:{}:{}:{}".format(
                    __class__.__name__, "__saveprogramlog", e
                )
            ProgramLog(err_msg, "error")

    def __savedummyprogramlog():
        try:
            with File("/ProgramLogs/temp.log", "w") as f:
                SaveProgramLog(f)
        except Exception as e:
            if sys_allowed_flag:
                err_msg = "EXCEPTION:{}:{}:{}".format(
                    __class__.__name__,
                    sys._getframe().f_code.co_name,
                    traceback.format_exc(),
                )
            else:
                err_msg = "EXCEPTION:{}:{}:{}".format(
                    __class__.__name__, "__savedummyprogramlog", e
                )
            print(err_msg)
            ProgramLog(err_msg, "error")

    def __checkprogramlog(timer, count):
        ProgramLogSaver.__savedummyprogramlog()
        log = ProgramLogSaver.__readdummyprogramlog()
        if log != ProgramLogSaver.__cur_log:
            ProgramLogSaver.__cur_log = log
            ProgramLogSaver.__saveprogramlog()
            print("ProgramLogSaver: new log saved")

    def EnableProgramLogSaver():
        ProgramLogSaver.__save_timer = Timer(60, ProgramLogSaver.__checkprogramlog)
        ProgramLogSaver.__save_timer.Restart()

    def DisableProgramLogSaver():
        ProgramLogSaver.__save_timer.Stop()
