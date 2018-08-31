# This script has been modified to archive and upload frozen buckets to S3
# Modified by: Saad Butto
# Date: April 2018

import sys, os, gzip, shutil, subprocess, random, gnupg
import boto
import datetime
import time
import tarfile
# applyLogging is a python script named applyLogging.py that exists at the same level of this script.
# If the file applyLogging.py doesn't exist where this file is located, the import statement will fail.
sys.path.append(script_path)
import applyLogging

### CHANGE THIS TO YOUR ACTUAL ARCHIVE DIRECTORY!!!
ARCHIVE_DIR = "/splunkdb/archived_indexes"
#ARCHIVE_DIR = os.path.join(os.getenv('SPLUNK_HOME'), 'frozenarchive')

script_path = '' #for the logging library
log_file_path = '' #Where you want the ascript to log to. For example /var/log/splunk_archive.log
gnu_home_dir = '' #where the gpg directory is. For example /home/s3/.gnupg/
reciepient_email = '' #the email the gpg uses to encrypt the files

# Enabling the logging system
logger = applyLogging.get_module_logger(app_name='SplunkArchive',file_path=log_file_path)

#####################################################################################################
# Finding out the epoch value at four month ago so we can copmare the bucket timestamp against it.
#####################################################################################################

# First we need to find today's epoch
today=round(time.mktime(datetime.datetime.today().timetuple()))
# Substract 120 days
one_month_earlier=today-120*86400

logger.info('Started on '+str(datetime.datetime.today()))

# Getting the hostname so we can prefix the uploaded file name with it to distinguish buckets from different indexes.
hostname=os.uname()[1]

# S3 creds
AWS_ACCESS_KEY_ID="xxxxxxxx"
AWS_ACCESS_KEY_SECRET="xxxxxxxx"
AWS_BUCKET_NAME="Bucket_Name_in_S3"

# Creating the gpg object
gpg = gnupg.GPG(gnupghome=gnu_home_dir)

# For new style buckets (v4.2+), we can remove all files except for the rawdata.
# We can later rebuild all metadata and tsidx files with "splunk rebuild"
def handleNewBucket(base, files):
        logger.info('Archiving bucket: ' + base)
        print 'Archiving bucket: ' + base
        for f in files:
                full = os.path.join(base, f)
                if os.path.isfile(full):
                        os.remove(full)

# For buckets created before 4.2, simply gzip the tsidx files
# To thaw these buckets, be sure to first unzip the tsidx files
def handleOldBucket(base, files):
        print 'Archiving old-style bucket: ' + base
        logger.info('Archiving old-style bucket: ' + base)
        for f in files:
                full = os.path.join(base, f)
                if os.path.isfile(full) and (f.endswith('.tsidx') or f.endswith('.data')):
                        fin = open(full, 'rb')
                        fout = gzip.open(full + '.gz', 'wb')
                        fout.writelines(fin)
                        fout.close()
                        fin.close()
                        os.remove(full)

# This function is not called, but serves as an example of how to do
# the previous "flatfile" style export. This method is still not
# recommended as it is resource intensive
def handleOldFlatfileExport(base, files):
        command = ['exporttool', base, os.path.join(base, 'index.export'), 'meta::all']
        retcode = subprocess.call(command)
        if retcode != 0:
                sys.exit('exporttool failed with return code: ' + str(retcode))

        for f in files:
                full = os.path.join(base, f)
                if os.path.isfile(full):
                        os.remove(full)
                elif os.path.isdir(full):
                        shutil.rmtree(full)
                else:
                        print 'Warning: found irregular bucket file: ' + full
                        logger.info('Warning: found irregular bucket file: ' + full)

# This function is to tar the bucket folder.
# S3 doesn't work like a regualr file structure. It allows us to create buckets that can store objects.
# Each object will hold the contents of a file.
def make_index_bucket_tarfile(output_filename,source_dir):
        with tarfile.open(output_filename, "w:gz") as tar:
                try:
                        # The file will be saved inside the bucket. The uplaod function will pick it up. The remove function will cean it out.
                        tar.add(source_dir,arcname=os.path.basename(source_dir))
                        logger.info(output_filename+' was created')
                except (OSError, tarfile.TarError), e:
                        logger.error('Error: tar archive creation failed')
                else:
                        shutil.rmtree(source_dir)
                        logger.info(os.path.basename(source_dir)+' was removed')

# Here we use this function to encrypt the tarred files befpre uploading them to the S3
def gpg_tared_bucket(output_filename):
        encrypted_output_filename = output_filename+'.gpg'
        try:
                with open(output_filename, 'rb') as f:
                        status = gpg.encrypt_file(f, recipients=[reciepient_email],output=encrypted_output_filename,always_trust=True)
                logger.info(encrypted_output_filename+' was created')
                return encrypted_output_filename
        except (OSError), e:
                logger.error('Error: Bucket encryption failed')
        else:
                os.remove(output_filename)
                logger.info(os.path.basename(output_filename)+' was removed')

# This function will stream the file content out to S3 and stores it inside the bucket named above.
def upload_2_s3(full_comp_file_path):

        # Will use the base file name hostname_indexname_splunkbucketname.tar.gz as the S3 bucket object key
        filename=os.path.basename(full_comp_file_path)
        k = boto.s3.key.Key(bukt)
        k.key = filename
        # Streams out the file content to S3
        try:
                k.set_contents_from_filename(full_comp_file_path)
                logger.info(full_comp_file_path+' was pushed to S3.')
        except Exception:
                logger.warn(full_comp_file_path+' push to S3 failed')
        else:
                os.remove(full_comp_file_path)
                logger.info(full_comp_file_path+' was removed')

if __name__ == "__main__":
        if len(sys.argv) != 2:
                logger.info('usage: python coldToFrozenPlusS3Uplaod.py <bucket_dir_to_archive>')
                sys.exit('usage: python coldToFrozenPlusS3Uplaod.py <bucket_dir_to_archive>')

        if not os.path.isdir(ARCHIVE_DIR):
                try:
                        os.mkdir(ARCHIVE_DIR)
                except OSError:
                        # Ignore already exists errors, another concurrent invokation may have already created this dir
                        logger.info("mkdir warning: Directory '" + ARCHIVE_DIR + "' already exists"
                        sys.stderr.write("mkdir warning: Directory '" + ARCHIVE_DIR + "' already exists\n")

        bucket = sys.argv[1]
        if not os.path.isdir(bucket):
                logger.info('Given bucket is not a valid directory: ' + bucket)
                sys.exit('Given bucket is not a valid directory: ' + bucket)

        rawdatadir = os.path.join(bucket, 'rawdata')
        if not os.path.isdir(rawdatadir):
                logger.info('No rawdata directory, given bucket is likely invalid: ' + bucket)
                sys.exit('No rawdata directory, given bucket is likely invalid: ' + bucket)

        files = os.listdir(bucket)
        journal = os.path.join(rawdatadir, 'journal.gz')
        if os.path.isfile(journal):
                handleNewBucket(bucket, files)
        else:
                handleOldBucket(bucket, files)

        if bucket.endswith('/'):
                bucket = bucket[:-1]

        indexname = os.path.basename(os.path.dirname(os.path.dirname(bucket)))
        destdir = os.path.join(ARCHIVE_DIR, indexname, os.path.basename(bucket))

        # Defining the index name variable. We are uploading buckets within an index
        logger.info('archivedIndex= '+indexname)
        full_index_path=os.path.join(ARCHIVE_DIR,indexname)
        logger.info('Full Index Path= '+full_index_path)

        while os.path.isdir(destdir):
                logger.info('Warning: This bucket already exists in the archive directory. Adding a random extension to this directory...')
                print 'Warning: This bucket already exists in the archive directory'
                print 'Adding a random extension to this directory...'
                destdir += '.' + str(random.randrange(10))

        shutil.copytree(bucket, destdir)
        logger.info(bucket+' was archived in '+destdir)

        ###################################################################################
        # Using the boto module, we interact with the AWS S3 API
        ###################################################################################

        # Cerating the connection to S3
        try:
                        conn = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_ACCESS_KEY_SECRET)
                        logger.info('Connection created')
        except Exception:
                        logger.error('Amazon S3 conection failed')
                        exit(1)

        # Creating the bucket object. We are sure that the bucket name exists so we don't want to validate. Validation charges us money.
        try:
                        bukt = conn.get_bucket(AWS_BUCKET_NAME,validate=False)
                        logger.info('The bucket '+str(bukt)+' has been fetched')
        except Exception:
                        logger.error('Fetching Amazon Splunk bucket failed')
                        exit(1)

        # Starting the S3 push process
        for bucket_dir_name in os.listdir(full_index_path):
                full_bucket_path=os.path.join(full_index_path,bucket_dir_name)

                if os.path.isdir(full_bucket_path):
                        if os.path.getmtime(full_bucket_path) < one_month_earlier:
                                logger.info('Working on the bucket '+full_bucket_path)
                                logger.info('The Bucket is older than 120 days')
                                output_filename=full_index_path+'/'+hostname+'_'+indexname+'_'+bucket_dir_name+'.tar.gz'
                                make_index_bucket_tarfile(output_filename,full_bucket_path)
                                tarred_encrypted_ready_2_s3_file = gpg_tared_bucket(output_filename)
                                upload_2_s3(tarred_encrypted_ready_2_s3_file)


