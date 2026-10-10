from server.core import Store
from tests.test_platform import record


def test_ten_thousand_independent_records_remain_searchable(tmp_path):
    store = Store(tmp_path)
    records = [record(f'review-{n:05d}', body=f'Independent synthetic test record {n}') for n in range(10000)]
    store.import_catalog(records)
    assert store.search(q='证据', discipline='通用科研', stage='阅读综述', limit=30)['total'] == 10000
    result = store.search(q='review-09999')
    assert result['total'] == 1
    assert result['items'][0]['name'] == 'review-09999'
