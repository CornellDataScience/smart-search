import json
import uuid


data = json.load(open("summaries3.json"))
reformatted_data = {}
reformatted_data['summaries'] = []
reformatted_data['metadata'] = []
reformatted_data['ids'] = []
for summary_result in data:
    reformatted_data['summaries'].append(summary_result['summary'])
    metadata = summary_result['metadata']
    metadata['code'] = summary_result['code']
    reformatted_data['metadata'].append(metadata)
    #generate unique id
    unique_id = str(uuid.uuid4())
    reformatted_data['ids'].append(unique_id)
with open("vbd_formatted_summaries3.json", "w") as outfile:
    json.dump(reformatted_data, outfile, indent=4)