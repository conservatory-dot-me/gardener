from subprocess import call


def test_flake8():
    return_code = call(['flake8'])
    assert return_code == 0
