import asyncio

from server.benchmarks import execute_benchmark, prepare_benchmark
from server.core import Store
from server.providers import save_provider


def test_comparison_uses_model_selected_when_batch_was_created(tmp_path):
    store = Store(tmp_path)
    save_provider(store, {'id':'local', 'kind':'ollama', 'model':'original', 'base_url':'http://127.0.0.1:1'})
    batch = prepare_benchmark(store, {'template':'writing', 'provider_id':'local', 'budget':0, 'repetitions':1})
    save_provider(store, {'id':'local', 'kind':'ollama', 'model':'changed', 'base_url':'http://127.0.0.1:1'})
    asyncio.run(execute_benchmark(store, batch['id']))
    runs = store.list('runs')
    assert len(runs) == 1
    assert runs[0]['model'] == 'original'
    assert store.get('run-providers', runs[0]['id'])['model'] == 'original'


def test_cancelling_batch_does_not_start_remaining_trials(tmp_path):
    from unittest.mock import patch
    store = Store(tmp_path)
    save_provider(store, {'id':'local', 'kind':'ollama', 'model':'slow', 'base_url':'http://127.0.0.1:1'})
    batch = prepare_benchmark(store, {'template':'writing', 'provider_id':'local', 'budget':0, 'repetitions':3})

    async def scenario():
        started = asyncio.Event()
        async def slow_request(*args, **kwargs):
            started.set()
            await asyncio.sleep(30)
        # External transport is blocked deliberately to cancel during a request.
        with patch('server.execution.billed_completion', slow_request):
            job = asyncio.create_task(execute_benchmark(store, batch['id']))
            await started.wait()
            job.cancel()
            await asyncio.wait_for(job, 1)
    asyncio.run(scenario())
    assert store.get('benchmarks', batch['id'])['status'] == 'cancelled'
    assert sorted(r['status'] for r in store.list('runs')) == ['cancelled', 'not_run', 'not_run']


def test_insufficient_request_reservation_stops_the_whole_comparison(tmp_path):
    store = Store(tmp_path)
    save_provider(store, {'id':'paid', 'kind':'openai', 'model':'test', 'base_url':'http://127.0.0.1:1', 'api_key':'test-only', 'input_price':1, 'output_price':1})
    batch = prepare_benchmark(store, {'template':'writing', 'provider_id':'paid', 'budget':0.000001, 'repetitions':3})
    asyncio.run(execute_benchmark(store, batch['id']))
    assert store.get('benchmarks', batch['id'])['status'] == 'budget_exhausted'
    assert sorted(r['status'] for r in store.list('runs')) == ['budget_exhausted', 'not_run', 'not_run']
    assert store.budget(batch['id'])['spent'] == 0
