import argparse
import os



def upload_to_s3(forecast_datetime, output_path, level, keep):
    
    if output_path is None:
        output_dir = os.path.join(os.getcwd(), f"forecasts_{level}_levels")  # Use current directory if not specified
    else:
        output_dir = os.path.join(output_path, f"forecasts_{level}_levels")
        
    s3 = boto3.client('s3')

    date = forecast_datetime[0:8]
    time = forecast_datetime[8:10]

    # Upload output files to S3
    # Iterate over all files in the local directory and upload each one to S3
    s3_prefix = f'graphcastgfs.{date}/{time}/forecasts_{level}_levels'
    
    for root, dirs, files in os.walk(self.output_dir):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, local_directory)
            s3_path = os.path.join(s3_prefix, relative_path)
            
            # Upload the file
            s3.upload_file(local_path, self.s3_bucket_name, s3_path)

    print("Upload to s3 bucket completed.")

    # Delete local files if keep_data is False
    if not keep_data:
        # Remove forecasts data from the specified directory
        print("Removing downloaded grib2 data...")
        try:
            os.system(f"rm -rf {self.output_dir}")
            print("Downloaded data removed.")
        except Exception as e:
            print(f"Error removing downloaded data: {str(e)}")
            print("Local input and output files deleted.")
    

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="upload input and output to s3 bucket")
    parser.add_argument("-d", "--datetime", help="forecast datetime", required=True)
    parser.add_argument("-l", "--level", help="number of pressure levels", default=13)
    parser.add_argument("-o", "--output", help="output file path (including file name)", default=None)
    
    args = parser.parse_args()
    keep = False

    upload_to_s3(args.datetime, str(args.level), args.output, keep)
