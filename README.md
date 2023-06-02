# signal
Signal broadcasting

This small Python library provides a convenient way to 
broadcast signals to multiple listeners in a decoupled manner. 
It enables the implementation of event-driven architectures 
and facilitates communication between different components 
of an application.

## Features

- **Signal Definition**: Define custom signals using a 
simple and intuitive syntax.
- **Signal Broadcasting**: Broadcast signals to multiple 
listeners without direct dependencies.
- **Signal Subscription**: Register listeners to receive 
signals of interest.
- **Flexible Dispatching**: Control the behavior of signal 
dispatching, including synchronous or asynchronous processing.
- **Thread-Safe**: Safely broadcast signals in multithreaded 
or multiprocessing environments.
- **Extensible**: Easily integrate the library with 
existing codebases and frameworks.

## Installation

You can install the Signal using favorite package manager,
for example with pip:

```shell
pip install signal
```

## Usage

### Signal Definition

To define a signal, import the `Signal` class from the library 
and create an instance:

```python
from signal import Signal

signal = Signal()
```

alternatively, you can use the `a named signal`:

```python
signal = Signal('my_signal')
```

Trying to instantiate a signal with the same name will
return the same signal instance:

```python
signal1 = Signal('my_signal')
signal2 = Signal('my_signal')

assert signal1 is signal2
```

### Signal Broadcasting

To broadcast a signal, call the `fire` method of the signal
with relevant data:

```python
from signal import Signal

signal = Signal()

signal.fire()(data='Hello World!')
```

The `fire` method returns a callable that take parameters
to be passed to the listeners. The parameters can be 
positional or named.

`fire` method can be called with or without parameters:

```python
signal.fire(events=["my_event"])()
```

### Signal Subscription

To subscribe to a signal, use the `register` method of the
signal:

```python
from signal import Signal

signal = Signal()

def listener(data):
    print(data)

signal.register(listener)

signal.fire()(data='Hello World!')
```

A notable feature of this library, is that you can
decorate a class and class methods as callbacks. So,
all the instances of the decorated class will have
the decorated methods registered as callbacks:

```python
from signal import Signal

signal = Signal()

@signal.wire.cls
class MyClass:
    def __init__(self, name):
        self.name = name

    @signal.wire.cls_cb
    def listener(self, data):
        print(f'{self.name}: {data}')


instance1 = MyClass('instance1')
instance2 = MyClass('instance2')

signal.fire()(data='Hello World!')
# prints:
# instance1: Hello World!
# instance2: Hello World!
```

Sometimes you want that a signal handle several signals,
like channels in a message broker. To do that, you can
write:

```python
from signal import Signal

signal = Signal()

@signal.wire.cls
class MyClass:
    def __init__(self, name):
        self.name = name

    @signal.wire.on_event('my_event')
    def listener_a(self, data):
        print(f'{self.name}: {data}')

    @signal.wire.on_event('my_event_2')
    def listener_b(self, data):
        print(f'{self.name}: {data}')

instance1 = MyClass('instance1')

signal.fire(events=['my_event'])(data='Hello World!')
# calls listener_a
```

You can also specify a receiver for a signal, with the code
above:

```python
instance1 = MyClass('instance1')
instance2 = MyClass('instance2')

signal.fire(events=['my_event'], receiver=instance1)(data='Hello World!')

# only instance1 receives the signal
```

You can also specify dependencies between events of the same
signal:

```python

from signal import Signal

signal = Signal()

@signal.wire.fn(event="fn_event", depends_on={"my_cls_event"})
def on_processing_data():
    print("processing data ended !")

@signal.wire.cls
class MyClass:
    def __init__(self, name):
        self.name = name

    @signal.wire.on_event('my_cls_event')
    def listener(self):
        print(f'{self.name}: Hello World!')


instance = MyClass('instance1')

signal.fire(events=['fn_event'])()

# because fn_event depends on my_cls_event, my_cls_event is called first
# automatically

```

You can also get all path of dependencies between events of the same
signal:

```python
events_to_fire_in_order = signal.get_event_path("fn_event")
print(events_to_fire_in_order)
# prints:
#[['my_cls_event', 'fn_event']]
```

### Asynchronous Signal Processing

By default, signals are processed synchronously. However,
you can specify that a signal should be processed in an
asynchronous manner. All synchronous listeners will be
run in a separate thread.

```python
signal = Signal()

...

await signal.fire_async()(data='Hello World!')
```

## Contribution

Contributions are welcome! If you find any issues or have suggestions for improvement, please open an issue or submit a pull request on the GitHub repository.

## License
`MIT`