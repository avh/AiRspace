# (c)2018-2020, Artfahrt Inc, Arthur van Hoff

import os, zipfile, tqdm
import boto3, botocore, requests, tempfile
import common.settings as settings
from common.datastore import DataStore

#
# Download a chart file from the FAA and upload it to S3
#
def download_chart(s3, url:str, path:str) -> bool:
    try:
        s3.head_object(Bucket=settings.BUCKET, Key=f"{path}/.downloaded")
        print(f"{path} already exists")
        return True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] != "404":
            pass
    print(f"downloading {url} to s3://{settings.BUCKET}/{path}")
       
    with tempfile.NamedTemporaryFile() as src:
        print("TEMPFILE", src.name)
        with requests.get(url, stream=True) as req:
            if req.status_code != 200:
                print("failed to download %s" % (url))
                return False
            with tqdm.tqdm(total=int(req.headers['Content-length'])) as progress:
                for chunk in req.iter_content(chunk_size=1024*1024):
                    src.write(chunk)
                    progress.update(len(chunk))
        src.seek(0)
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(src.name) as zip:
                zip.extractall(tmpdir)
            for name in os.listdir(tmpdir):
                print("uploading", name)
                s3.upload_file(os.path.join(tmpdir, name), settings.BUCKET, f"{path}/{name}")
            with tempfile.NamedTemporaryFile() as empty:
                s3.upload_file(empty.name, settings.BUCKET, f"{path}/.downloaded")
    return True
   
def lambda_handler(event, context):
    #print('EVENT', event)
    s3 = boto3.client('s3')
    db = DataStore()
    table = db['chart_list']
    count = 0
    for rec in event['Records']:
        if rec['eventName'] in ('INSERT', 'UPDATE'):
            name = rec['dynamodb']['Keys']['key']['S']
            chart = table[name]
            if chart is None:
                print(f"CHART NOT FOUND: {name}")
            elif download_chart(s3, chart['href'], chart['path']):
                count += 1
    return count

if __name__ == '__main__':
    event = {"Records":[{"Keys":{"key":{"S":"Albuquerque"}}}]}
    result = lambda_handler(event, None)
    print(result)