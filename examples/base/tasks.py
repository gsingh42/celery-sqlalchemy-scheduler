# coding=utf-8
"""
Ready::

    $ pipenv install
    $ pipenv shell

Run Worker::

    # console 1 , in pipenv shell
    $ cd examples/base
    $ celery worker -A tasks:celery -l info

Run Beat::

    # console 2, in pipenv shell
    $ cd examples/base
    $ celery beat -A tasks:celery -S tasks:DatabaseScheduler -l info

Console 3::

    # console 3, in pipenv shell
    $ python -m doctest tasks.py


>>> import json
>>> from celery_sqlalchemy_scheduler.models import PeriodicTask, IntervalSchedule
>>> from celery_sqlalchemy_scheduler.session import SessionManager

>>> beat_dburi = 'sqlite:///schedule.db'
>>> session_manager = SessionManager()
>>> engine, Session = session_manager.create_session(beat_dburi)
>>> session = Session()

# Disable 'echo-every-3-seconds' task
>>> task = session.query(PeriodicTask).filter_by(name='echo-every-3-seconds').first()
>>> task.enabled = False
>>> session.add(task)
>>> session.commit()


>>> schedule = session.query(IntervalSchedule).filter_by(every=10, period=IntervalSchedule.SECONDS).first()
>>> if not schedule:
...     schedule = IntervalSchedule(every=10, period=IntervalSchedule.SECONDS)
...     session.add(schedule)
...     session.commit()

# Add 'add-every-10s' task
>>> task = PeriodicTask(
...     interval=schedule,
...     name='add-every-10s',
...     task='tasks.add',  # name of task.
...     args=json.dumps([1, 5])
... )
>>> session.add(task)
>>> session.commit()
>>> print('Add ' + task.name)
Add add-every-10s

>>> task.args=json.dumps([10, 2])
>>> session.add(task)
>>> session.commit()
"""
import os
import time
import platform
import datetime as dt
from datetime import timedelta

from celery import Celery
from celery import schedules

from celery_sqlalchemy_scheduler.schedulers import DatabaseScheduler  # noqa

# 加载环境变量
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path, override=True)

# 可以在 examples/base 目录下创建 .env 文件，修改对应的变量
ECHO_EVERY_MINUTE = os.getenv('ECHO_EVERY_MINUTE', '0')
ECHO_EVERY_HOUR = os.getenv('ECHO_EVERY_HOUR', '8')

if platform.system() == 'Windows':
    # Celery在Windows环境下运行需要设置这个变量，否则调用任务会报错
    os.environ['FORKED_BY_MULTIPROCESSING'] = '1'

backend = 'rpc://'
broker_url = 'amqp://guest:guest@127.0.0.1:5672//'


# 如果数据库修改了下面的schedule，beat重启后数据库会被下面的配置覆盖
beat_schedule = {
    'echo-every-3-seconds': {
        'task': 'tasks.echo',
        'schedule': timedelta(seconds=3),
        'args': ('hello', ),
        'options': {
            'expires': dt.datetime.utcnow() + timedelta(seconds=10)  # right
            # 'expires': dt.datetime.now() + timedelta(seconds=30)  # error
            # 'expires': 10  # right
        }
    },
    'add-every-minutes': {
        'task': 'tasks.add',
        'schedule': schedules.crontab('*', '*', '*'),
        'args': (1, 2)
    },
    'echo-every-hours': {
        'task': 'tasks.echo',
        'schedule': schedules.crontab(ECHO_EVERY_MINUTE, '*', '*'),
        'args': ('echo-every-hours',)
    },
    'echo-every-days': {
        'task': 'tasks.echo',
        'schedule': schedules.crontab(ECHO_EVERY_MINUTE, ECHO_EVERY_HOUR, '*'),
        'args': ('echo-every-days',)
    },
}

beat_scheduler = 'celery_sqlalchemy_scheduler.schedulers:DatabaseScheduler'

beat_sync_every = 0

# The maximum number of seconds beat can sleep between checking the schedule.
# default: 0
beat_max_loop_interval = 10

# 非celery和beat的官方配置，配置 celery_sqlalchemy_scheduler 的数据库路径
beat_dburi = 'sqlite:///schedule.db'
# beat_dburi = 'mysql+mysqlconnector://root:root@127.0.0.1/celery-schedule'

# 配置时区
timezone = 'Asia/Shanghai'

# 默认每个worker跑完10个任务后，自我销毁程序重建来释放内存
# 防止内存泄漏
worker_max_tasks_per_child = 10

celery = Celery('tasks',
                backend=backend,
                broker=broker_url)

config = {
    'beat_schedule': beat_schedule,
    # 'beat_scheduler': beat_scheduler,  # 命令行传参配置了，所以这里并不需要写死在代码里
    'beat_max_loop_interval': beat_max_loop_interval,
    'beat_dburi': beat_dburi,

    'timezone': timezone,
    'worker_max_tasks_per_child': worker_max_tasks_per_child
}

celery.conf.update(config)


@celery.task
def add(x, y):
    return x + y


@celery.task
def echo(data):
    print(data)


if __name__ == "__main__":
    celery.start()
    # import doctest
    # doctest.testmod()
