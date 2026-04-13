import requests
import json
import time

# Create decomposed job
print("Creating decomposed job...")
response = requests.post('http://127.0.0.1:8000/jobs/decompose', json={
    'instruction': 'Run a weather simulation for North America and validate results',
    'priority': 100
})

result = response.json()
job_id = result['job_id']
print(f'\nJob created: ID {job_id}')
print(f'Tasks: {len(result["graph"]["tasks"])}')
for task in result['graph']['tasks']:
    deps = task.get('depends_on', [])
    print(f'  - {task["id"]}: {task["name"]} (depends on: {deps})')

# Monitor execution
print(f'\nMonitoring job {job_id} execution...\n')
for i in range(25):
    response = requests.get(f'http://127.0.0.1:8000/jobs/{job_id}')
    job = response.json()
    status = job['status']
    progress = job['progress']
    attempts = job['attempts']
    
    checkpoint = json.loads(job.get('checkpoint', '{}'))
    completed = checkpoint.get('completed', [])
    
    print(f'[{i:2d}s] Status: {status:<10} Progress: {progress:>3}% Completed tasks: {completed}')
    
    if status in ['completed', 'failed', 'cancelled']:
        print(f'\nJob finished with status: {status}')
        break
    
    time.sleep(1)
