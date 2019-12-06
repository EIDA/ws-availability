import logging.config
import os

# Create logging
try:
    RUNMODE = os.environ["RUNMODE"]
except Exception as ex:
    print(str(ex))

CONFIG_FILE = "logging_config_" + str(RUNMODE) + ".ini"
FILE_DIR = os.path.dirname(__file__)

try:
    os.makedirs(FILE_DIR + "/logs")
except OSError as ex:
    print(str(ex))

logging.config.fileConfig(os.path.join(FILE_DIR, "apps", CONFIG_FILE))

main_log = logging.getLogger("root")
main_log.debug("RUNMODE variable successfully loaded: RUNMODE = %s " % RUNMODE)
main_log.debug("Logs directory successfully created in: %s" % FILE_DIR)
