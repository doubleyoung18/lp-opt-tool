"""Tests for quantization"""
import numpy as np
import unittest
import os
import yaml
import tensorflow as tf
import importlib

def build_fake_yaml():
    fake_yaml = '''
        model:
          name: fake_yaml
          framework: tensorflow
          inputs: x
          outputs: op_to_store
        device: cpu
        evaluation:
          accuracy:
            metric:
              topk: 1
        tuning:
            strategy:
              name: mse
            accuracy_criterion:
              relative: 0.01
            workspace:
              path: saved
        '''
    y = yaml.load(fake_yaml, Loader=yaml.SafeLoader)
    with open('fake_yaml.yaml',"w",encoding="utf-8") as f:
        yaml.dump(y,f)
    f.close()

def build_fake_yaml2():
    fake_yaml = '''
        model:
          name: fake_yaml
          framework: tensorflow
          inputs: x
          outputs: op_to_store
        device: cpu
        evaluation:
          accuracy:
            metric:
              topk: 1
        tuning:
          strategy:
            name: mse
          exit_policy:
            max_trials: 5
          accuracy_criterion:
            relative: -0.01
          workspace:
            path: saved
        '''
    y = yaml.load(fake_yaml, Loader=yaml.SafeLoader)
    with open('fake_yaml2.yaml',"w",encoding="utf-8") as f:
        yaml.dump(y,f)
    f.close()

def build_fake_model():
    try:
        graph = tf.Graph()
        graph_def = tf.GraphDef()
        with tf.Session() as sess:
            x = tf.placeholder(tf.float64, shape=(1,3,3,1), name='x')
            y = tf.constant(np.random.random((2,2,1,1)), name='y')
            op = tf.nn.conv2d(input=x, filter=y, strides=[1,1,1,1], padding='VALID', name='op_to_store')

            sess.run(tf.global_variables_initializer())
            constant_graph = tf.graph_util.convert_variables_to_constants(sess, sess.graph_def, ['op_to_store'])

        graph_def.ParseFromString(constant_graph.SerializeToString())
        with graph.as_default():
            tf.import_graph_def(graph_def, name='')
    except:
        graph = tf.Graph()
        graph_def = tf.compat.v1.GraphDef()
        with tf.compat.v1.Session() as sess:
            x = tf.compat.v1.placeholder(tf.float64, shape=(1,3,3,1), name='x')
            y = tf.compat.v1.constant(np.random.random((2,2,1,1)), name='y')
            op = tf.nn.conv2d(input=x, filters=y, strides=[1,1,1,1], padding='VALID', name='op_to_store')

            sess.run(tf.compat.v1.global_variables_initializer())
            constant_graph = tf.compat.v1.graph_util.convert_variables_to_constants(sess, sess.graph_def, ['op_to_store'])

        graph_def.ParseFromString(constant_graph.SerializeToString())
        with graph.as_default():
            tf.import_graph_def(graph_def, name='')
    return graph

class TestQuantization(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        self.constant_graph = build_fake_model()
        build_fake_yaml()
        build_fake_yaml2()

    @classmethod
    def tearDownClass(self):
        os.remove('fake_yaml.yaml')
        os.remove('fake_yaml2.yaml')
        os.remove('saved/history.snapshot')
        os.remove('saved/deploy.yaml')
        os.rmdir('saved')

    def test_ru_mse_one_trial(self):
        from ilit.strategy import strategy
        from ilit import Quantization

        quantizer = Quantization('fake_yaml.yaml')
        dataset = quantizer.dataset('dummy', (100, 3, 3, 1), label=True)
        dataloader = quantizer.dataloader(dataset)
        quantizer(
            self.constant_graph,
            q_dataloader=dataloader,
            eval_dataloader=dataloader
        )

    def test_ru_mse_max_trials(self):
        from ilit.strategy import strategy
        from ilit import Quantization

        quantizer = Quantization('fake_yaml2.yaml')
        dataset = quantizer.dataset('dummy', (100, 3, 3, 1), label=True)
        dataloader = quantizer.dataloader(dataset)
        quantizer(
            self.constant_graph,
            q_dataloader=dataloader,
            eval_dataloader=dataloader
        )

    def test_loss_calculation(self):
        from ilit.strategy.tpe import TpeTuneStrategy
        from ilit import Quantization

        quantizer = Quantization('fake_yaml.yaml')
        dataset = quantizer.dataset('dummy', (100, 3, 3, 1), label=True)
        dataloader = quantizer.dataloader(dataset)
        testObject = TpeTuneStrategy(self.constant_graph, quantizer.conf, dataloader)
        testObject._calculate_loss_function_scaling_components(0.01, 2, testObject.loss_function_config)
        # check if latency difference between min and max corresponds to 10 points of loss function
        tmp_val = testObject.calculate_loss(0.01, 2, testObject.loss_function_config)
        tmp_val2 = testObject.calculate_loss(0.01, 1, testObject.loss_function_config)
        self.assertTrue(True if int(tmp_val2 - tmp_val) == 10 else False)
        # check if 1% of acc difference corresponds to 10 points of loss function
        tmp_val = testObject.calculate_loss(0.02, 2, testObject.loss_function_config)
        tmp_val2 = testObject.calculate_loss(0.03, 2, testObject.loss_function_config)
        self.assertTrue(True if int(tmp_val2 - tmp_val) == 10 else False)

if __name__ == "__main__":
    unittest.main()
