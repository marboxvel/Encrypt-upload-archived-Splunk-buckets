# Encrypt-upload-archived-Splunk-buckets

How the indexer archives data


The indexer rotates old data out of the index based on your data retirement policy, as described in Set a retirement and archiving policy. Data moves through several stages, which correspond to file directory locations. Data starts out in the hot database, located as subdirectories ("buckets") under /splunkdb/index_name/db/. It then moves to the warm database, also located as subdirectories under /splunkdb/index_name/db. Eventually, data is aged into the cold database /splunkdb/index_name/colddb.


Finally, data reaches the frozen state. This can happen for a number of reasons, as described in Set a retirement and archiving policy. At this point, the indexer erases the data from the index. If you want the indexer to archive the frozen data before erasing it from the index, you must specify that behavior.
Specify an archiving script


If you set the coldToFrozenScript attribute in indexes.conf, the script you specify will run just before the indexer erases the frozen data from the index.
You'll need to supply the actual script. Typically, the script will archive the data, but you can provide a script that performs any action you want.

In Splunk cluster setup:
Add this stanza to /opt/splunk/etc/master-apps/_cluster/local/indexes.conf:
Indexes.conf
[<index>]
coldToFrozenScript = ["<path to program that runs script>"] "<path to script>"


Note the following:

<index> specifies which index contains the data to archive.
<path to script> specifies the path to the archiving script. The default script is in $SPLUNK_HOME/bin or one of its subdirectories.
<path to program that runs script> is optional. You must set it if your script requires a program, such as python, to run it.


Indexes.conf
coldToFrozenScript = "/bin/python" "/scripts/splunk_archive_script/coldToFrozenPlusS3Uplaod.py"
 
 1- Verify that the following packages are installed.
    Most likely installed by default: sys, os, gzip, shutil, subprocess, random, datetime, time, tarfile, logging
    Will need to be installed: boto, gnupg
    python2-boto.noarch
    python2-gnupg.noarch

 2- A logging module is written so the script can log to /var/log/splunk_archive.log (needed to be set in the script). The module must exist where the archive script is stored, /scripts/splunk_archive_script/coldToFrozenPlusS3Uplaod.py.
    The module name is applyLogging.py

 3- Don't use the Python shipped with Splunk, coldToFrozenScript = "$SPLUNK_HOME/bin/python", it doesn't have boto and gnupg installed, but make sure to use coldToFrozenScript = "/bin/python"

