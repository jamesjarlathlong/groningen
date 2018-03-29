import tensorflow as tf
import numpy as np
from data import tile_creater
def _format_label(label):
	"""
	Args: label is like (53.223, 6.949, 3.0, 0.502994544, 'knmi2018etrn',...)
	(oneevent['eventlat'],oneevent['eventlon']
            ,oneevent['eventdepth'], oneevent['magnitude']
            ,oneevent['eventid'], topleft, sizex, sizey, numx,numy)
    Returns: onehot tile encoding - numpy array
	"""
	return 
def _parse_function(filename, label):
	"""load and format the data"""
	formatted_label = _format_label(label)
	return example, formatted_label
def load_data(filenames, labels):
	tf_filenames = tf.constant(filenames)
	#e.g.(["/var/data/image1.jpg", "/var/data/image2.jpg", ...])
	tf_labels = tf.constant(labels)
	dataset = tf.data.Dataset.from_tensor_slices((tf_filenames, tf_labels))#fill in
	dataset=dataset.map(_parse_function)
	return dataset
def train_input_fn(filenames, labels, batchsize=20):
	dataset = load_data(filenames, labels)
	# Shuffle, repeat, and batch the examples.
    dataset = dataset.shuffle(1000).repeat(100).batch(batch_size)
    # Return the dataset.
    iterator = dataset.make_one_shot_iterator()
    data, labels = iterator.get_next()
    return data, labels

def test_input_fn(filenames, labels, batchsize=20):
	dataset = load_data(filenames, labels)
    # Batch the examples
    assert batch_size is not None, "batch_size must not be None"
    dataset = dataset.batch(batch_size)
    # Return the dataset.
    iterator = dataset.make_one_shot_iterator()
    data, labels = iterator.get_next()
    return data, labels


def main(train_x, train_y, test_x, test_y):
    my_feature_columns = [tf.feature_column.numeric_column(key=str(k))
                          for k in range(10)]

    # Build 2 hidden layer DNN with 10, 10 units respectively.
    classifier = tf.estimator.DNNClassifier(
        feature_columns=my_feature_columns,
        # The model must choose between 4 classes
        n_classes=4,
        # Two hidden layers of 100 nodes each.
        hidden_units=[100, 100]
        )

    # Train the Model.
    classifier.train(input_fn=lambda:train_input_fn(train_x, train_y))

    # Evaluate the model.
    eval_result = classifier.evaluate(
        input_fn=lambda:test_input_fn(test_x, test_y))

    print('\nTest set accuracy: {accuracy:0.3f}\n'.format(**eval_result))
    predictions = classifier.predict(
        input_fn=lambda:test_input_fn(test_x,test_y))
   	
if __name__=='__main__':
	main(train_x, train_y, test_x, test_y)