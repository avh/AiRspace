# (c)2023, Arthur van Hoff, Artfahrt Inc

import boto3
import json

class DataStoreTable:
    def __init__(self, db, name:str):
        self.db = db
        self.name = name

    def __setitem__(self, key:str, value:dict):
        response = self.db.put_item(TableName=self.name, Item={'key': {'S': key}, 'value': {'S': json.dumps(value)}})
        #print('__setitem__', response)
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200

    def __getitem__(self, key:str) -> dict:
        response = self.db.get_item(TableName=self.name, Key={'key': {'S': key}})
        #print('__getitem__', response)
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200
        return json.loads(response['Item']['value']['S']) if 'Item' in response else None
    
    def __delitem__(self, key:str):
        response = self.db.delete_item(TableName=self.name, Key={'key': {'S': key}})
        #print('__delitem__', response)
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200

    def keys(self) -> iter:
        response = self.db.scan(TableName=self.name, AttributesToGet=['key'])
        #print('scan', response)
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200
        for item in response['Items']:
            yield item['key']['S']
        while 'LastEvaluatedKey' in response:
            response = self.db.scan(TableName=self.name, ExclusiveStartKey=response['LastEvaluatedKey'], AttributesToGet=['key'])
            #print('scan-more', response)
            assert response['ResponseMetadata']['HTTPStatusCode'] == 200
            for item in response['Items']:
                yield item['key']['S']
    
    def scan(self) -> iter:
        response = self.db.scan(TableName=self.name)
        #print('scan', response)
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200
        for item in response['Items']:
            yield (item['key']['S'], json.loads(item['value']['S']))
        while 'LastEvaluatedKey' in response:
            response = self.db.scan(TableName=self.name, ExclusiveStartKey=response['LastEvaluatedKey'])
            print('scan-more', response)
            assert response['ResponseMetadata']['HTTPStatusCode'] == 200
            for item in response['Items']:
                yield (item['key']['S'], json.loads(item['value']['S']))
    
    def clear(self):
        for key in list(self.keys()):
            del self[key]

    def __len__(self) -> int:
        return len(list(self.keys()))
    
    def __str__(self) -> str:
        return f'DataStoreTable(name={self.name},len={len(self)})'

class DataStore:
    def __init__(self):
        self.db = boto3.client('dynamodb')
        self.tables = self.db.list_tables()['TableNames']

    def __getitem__(self, name:str) -> DataStoreTable:
        if name not in self.tables:
            response = self.db.create_table(
                TableName=name,
                AttributeDefinitions=[{'AttributeName': 'key', 'AttributeType': 'S'}],
                KeySchema=[{'AttributeName': 'key', 'KeyType': 'HASH'}],
                BillingMode='PAY_PER_REQUEST'
            )
            #print("create_table", response)
            assert response['ResponseMetadata']['HTTPStatusCode'] == 200
            self.tables.append(name)

        return DataStoreTable(self.db, name)

if __name__ == '__main__':
    ds = DataStore()
    table = ds['test_table']
    table.clear()
    table['test_key1'] = {'test':None}
    table['test_key2'] = {'foobar':123}
    table['test_key3'] = "wunderbar"
    print(table['test_key'])
    print(table['test_key1'])
    print(table['test_key2'])
    print(table['test_key3'])
    del table['test_key2']
    del table['test_key5']
    print('keys', sorted(list(table.keys())))

    for key, value in table.scan():
        print('scan', key, value)
    
    print('len', len(table))