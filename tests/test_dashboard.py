from streamlit.testing.v1 import AppTest
from pathlib import Path
from test_platform import uid
import core

def test_dashboard_pages(uid):
    user,name=uid
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=30)
    app.run();assert not app.exception
    app.session_state['token']=core.login(name,'x');app.run()
    assert not app.exception
    for page in ['Transactions','Network explorer','GraphRAG engine','Detection center','Knowledge repository','Investigation cases','Overview']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, f'{page}: {app.exception}'
    app.sidebar.radio[0].set_value('GraphRAG engine').run()
    next(b for b in app.button if b.label=='Generate evidence-grounded brief').click().run()
    assert not app.exception
    assert app.session_state['result']['transactions']
