import json

from server.benchmarks import grade
from server.core import Store


def test_analysis_cannot_pass_with_fabricated_json_without_executed_code(tmp_path):
    store=Store(tmp_path)
    directory=tmp_path/'projects'/'p'/'runs'/'r'/'outputs'
    directory.mkdir(parents=True)
    (directory/'result.json').write_text(json.dumps({'mean':3,'std':1.58113883,'n':5}))
    run={'id':'r','project_id':'p','status':'completed','events':[]}
    assert grade(store,run,'analysis')[0] == 0


def test_literature_requires_title_and_date_in_output_not_only_doi(tmp_path):
    store=Store(tmp_path)
    run={'id':'r','project_id':'p','status':'completed','output':'10.1038/nature14539',
         'events':[{'action':'crossref_doi','result':{'records':[{'DOI':'10.1038/nature14539','title':['Deep learning'],'published':{'date-parts':[[2015,5,27]]}}]}}]}
    assert grade(store,run,'literature')[0] == 0
    run['output']='Deep learning (2015), DOI: 10.1038/nature14539'
    assert grade(store,run,'literature')[0] == 1


def test_blind_plot_review_provides_preview_without_candidate_identifier(tmp_path):
    from fastapi.testclient import TestClient

    from server.app import create_app
    with TestClient(create_app(tmp_path, tmp_path/'missing.json')) as client:
        store = client.app.state.store
        name = 'runs/secret-run/outputs/figure.png'
        path = tmp_path/'projects/p'/name
        path.parent.mkdir(parents=True)
        png = b'\x89PNG\r\n\x1a\n' + b'fixture'
        path.write_bytes(png)
        store.save('runs', {'id':'secret-run','project_id':'p','output':'图表说明','artifacts':[{'name':name}]})
        store.save('benchmarks', {'id':'b','results':[{'run_id':'secret-run','candidate':'secret-skill'}]})
        response = client.get('/api/v1/benchmarks/b/blind')
        assert 'secret-run' not in response.text and 'secret-skill' not in response.text
        image = response.json()[0]['images'][0]
        assert client.get(image).content == png
