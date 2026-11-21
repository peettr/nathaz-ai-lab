"""NeuralIF 467b760 / PyG 2.8 runtime interface adapter; no upstream edits."""
import inspect, abc
from torch_geometric.transforms import BaseTransform

def apply():
    from neuralif import models, utils
    affected=[]
    for module in (models, utils):
        for name, cls in vars(module).items():
            if (inspect.isclass(cls) and cls.__module__ == module.__name__
                    and issubclass(cls, BaseTransform)
                    and '__call__' in cls.__dict__ and 'forward' not in cls.__dict__):
                original=cls.__dict__['__call__']
                cls.forward=original
                # BaseTransform.__call__ dispatches to forward on modern PyG.
                cls.__call__=BaseTransform.__call__
                abc.update_abstractmethods(cls)
                affected.append(module.__name__+'.'+name)
    return affected
