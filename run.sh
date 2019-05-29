#!/usr/bin/env bash
set -euf

base_dir=$(cd `dirname $0` && pwd)
cd ${base_dir}

hostname=$(hostname)
created_env=0
created_venv=0

if [ ! -f ".env" ]
then
    secret_key=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 128 | head -n 1)
    echo "Configuring .env"
    cp .env.sample .env
    sed -i "s/__set_your_secret_key_here__/${secret_key}/g" .env
    created_env=1
fi

if [ ! -d "venv" ]
then
    echo "Creating venv"
    python -m venv --system-site-packages venv
    created_venv=1
fi

echo "Installing requirements"
venv/bin/pip install -r requirements.txt && venv/bin/pip install --upgrade pip

echo "Running migrate"
venv/bin/python manage.py migrate

echo "Running collectstatic"
venv/bin/python manage.py collectstatic --noinput

if [ ${created_env} -eq 1 ] && [ ${created_venv} -eq 1 ]
then
    echo "Loading initial data"
    venv/bin/python manage.py flush --noinput
    venv/bin/python manage.py loaddata initial_data.json

    echo "Creating admin user"
    venv/bin/python manage.py createsuperuser --username admin --email admin@localhost --noinput
    password=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 12 | head -n 1)
    venv/bin/python -c "import os; \
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gardener.settings'); \
        import django; django.setup(); \
        from django.contrib.auth.models import User; \
        user = User.objects.get(username='admin'); \
        user.set_password('${password}'); \
        user.save()"

    echo ""
    echo "*** IMPORTANT ***"
    echo "Please change the admin password printed below as soon as you are logged in into the admin page."
    echo "Username: admin"
    echo "Password: ${password}"
    echo ""
fi

if [ ! -f "gardener/device/drivers/odroid_c2_16x2_lcd" ] && [ ${hostname} = "gardener" ]
then
    echo "Building LCD driver"
    cd gardener/device/drivers
    make
    cd ${base_dir}
fi

if [ -f "supervisord.pid" ]
then
    pid=$(cat supervisord.pid)
    owner=$(stat -c "%U" supervisord.pid)
    if ps -p $pid > /dev/null && [ ${owner} == "gardener" ]
    then
        echo "Restarting supervisord with PID=${pid}"
        kill -HUP ${pid}
    else
        echo "supervisord with PID=${pid} is not running, starting supervisord"
        venv/bin/supervisord -c supervisord.conf
    fi
else
    echo "Starting supervisord"
    venv/bin/supervisord -c supervisord.conf
fi

if [ ! -f "nginx.conf" ] && [ ${hostname} = "gardener" ]
then
    echo "Configuring nginx.conf"
    cp nginx.conf.sample nginx.conf &&
        cd /etc/nginx/sites-enabled &&
        sudo rm -f default gardener.conf &&
        sudo ln -s $HOME/gardener/nginx.conf gardener.conf &&
        sudo service nginx start
        sudo service nginx reload
    cd ${base_dir}
fi

if [ ${hostname} = "gardener" ]
then
    echo "Installing crontab"
    crontab crontab.txt
fi

echo ""
echo "*** READY ***"
cd ${base_dir}
venv/bin/python manage.py get_urls
echo ""
