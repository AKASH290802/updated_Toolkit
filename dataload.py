# dataload.py
import pandas as pd
import dataset.Connections as Connections
import logging
from concurrent.futures import ThreadPoolExecutor

# Basic logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dataload.log'),
        logging.StreamHandler()
    ]
)

def process_batch(sf, records, object_name, external_id_field, batch_size=10000):
    """Upsert a batch of records to Salesforce."""
    try:
        results = Connections.bulk_upsert_salesforce(
            sf, object_name, records, external_id_field, batch_size
        )
        successes = sum(1 for batch in results for r in batch if r['success'])
        logging.info(f"Batch upserted: {successes}/{len(records)} records successful")
        return successes, len(records)
    except Exception as e:
        logging.error(f"Batch failed: {e}")
        return 0, len(records)

def main():
    try:
        # Get connections
        SQL, engine = Connections.get_sql_connection(file_path=r"C:\DM_toolkit\Services\linkedservices.json")
        SalesForce = Connections.get_salesforce_connection(file_path=r"C:\DM_toolkit\Services\linkedservices.json")

        # Query parameters
        query = "SELECT * FROM stg.account"
        batch_size = 20000  # Total batch size
        sf_batch_size = 10000  # Salesforce Bulk API batch size
        threads = 2
        total_records = 100_000_000  # Estimated total

        # Process batches with threading
        successes = 0
        processed = 0
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = []
            for chunk in Connections.run_sql_query(SQL, query, chunksize=batch_size):
                # Transform to Salesforce format
                records = chunk.rename(columns={
                    'Id': 'External_Id__c',
                    'Name': 'Name',
                    'Description': 'Description'
                }).to_dict('records')

                # Submit batch to thread pool
                futures.append(
                    executor.submit(
                        process_batch,
                        SalesForce,
                        records,
                        'Account',
                        'External_Id__c',
                        sf_batch_size
                    )
                )
                processed += len(records)
                logging.info(f"Processed {processed:,}/{total_records:,} records")

                # Limit active futures
                if len(futures) >= threads * 2:
                    for future in futures:
                        s, p = future.result()
                        successes += s
                    futures = []

            # Process remaining futures
            for future in futures:
                s, p = future.result()
                successes += s

        logging.info(f"Completed: {successes:,}/{processed:,} records successful")

    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        if 'SQL' in locals():
            SQL.close()
        if 'engine' in locals():
            engine.dispose()

if __name__ == "__main__":
    main()