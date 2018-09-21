from keras.layers import (
    Input,
    Dense,
    Conv2D,
    MaxPooling2D,
    UpSampling2D,
    BatchNormalization,
    Flatten,
    Reshape,
)
from keras.optimizers import Adam, RMSprop, Adadelta, Adagrad
from keras.utils import plot_model
from keras.models import Model
from trainingmonitor import TrainingMonitor
import argparse
import h5py
import matplotlib.pyplot as plt
import numpy as np
import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

EPOCHS = 10  # max 5 or 10
BATCH_SIZE = 2
# https://keras.io/optimizers
# OPTIMIZER = Adam(lr=0.001, amsgrad=True)
# OPTIMIZER = RMSprop()
OPTIMIZER = Adadelta(lr=1.0, rho=0.95, epsilon=None, decay=0.0)
# OPTIMIZER = Adagrad(lr=0.05)

ap = argparse.ArgumentParser()
ap.add_argument("-lw", "--load_weights", help="Path to the file weights")
ap.add_argument(
    "-d", "--dataset", default="packaging-dataset", help="path to input dataset"
)
args = vars(ap.parse_args())


def readFile(gender, dataset, X_img=None, x_gender=None, y_age=None):
    print("Reading", gender, dataset, "data...")
    file_name = gender + "-" + dataset + ".hdf5"
    with h5py.File(os.path.join(__location__, args["dataset"], file_name), "r+") as f:
        f_img = f["img"][()]
        f_gender = f["gender"][()]
        f_age = f["age"][()]
        f.close()
    if X_img is None:
        X_img = f_img
    else:
        X_img = np.concatenate((X_img, f_img), axis=0)

    if x_gender is None:
        x_gender = f_gender
    else:
        x_gender = np.concatenate((x_gender, f_gender), axis=0)

    if y_age is None:
        y_age = f_age
    else:
        y_age = np.concatenate((y_age, f_age), axis=0)

    return X_img, x_gender, y_age


################################# Auto encoder #################################
def encodedModel(inputs):
    x = Conv2D(1024, kernel_size=(3, 3), padding="same", activation="relu")(inputs)
    x = MaxPooling2D(pool_size=(4, 4), padding="same")(x)
    # x = Conv2D(256, kernel_size=(3, 3), activation="relu", padding="same")(x)
    # x = MaxPooling2D(pool_size=(2, 2), padding="same")(x)
    x = Conv2D(128, kernel_size=(3, 3), activation="relu", padding="same")(x)
    x = MaxPooling2D(pool_size=(2, 2), padding="same")(x)
    encoded = Conv2D(
        64, kernel_size=(3, 3), activation="relu", padding="same", name="encoded"
    )(x)
    encoded = Flatten()(encoded)
    return encoded


def decodedModel(inputs):
    inputs = Reshape((56, 56, -1))(inputs)
    x = Conv2D(64, kernel_size=(1, 1), activation="relu", padding="same")(inputs)
    x = UpSampling2D(size=(2, 2))(x)
    x = Conv2D(128, kernel_size=(3, 3), activation="relu", padding="same")(x)
    x = UpSampling2D(size=(2, 2))(x)
    x = Conv2D(256, kernel_size=(3, 3), activation="relu", padding="same")(x)
    x = UpSampling2D(size=(2, 2))(x)
    # x = Conv2D(512, kernel_size=(3, 3), activation="relu", padding="same")(x)
    # x = UpSampling2D(size=(2, 2))(x)
    decoded = Conv2D(
        3, kernel_size=(3, 3), padding="same", activation="sigmoid", name="decoder"
    )(x)
    return decoded


################################# Auto encoder #################################


# Run presses if this file is main
if __name__ == "__main__":
    # Path to save model
    PATH_SAVE_MODEL = os.path.join(__location__, "model_backup", "autoencoder")
    # Save model fit progress
    PATH_TRAING_MONITOR = os.path.join(PATH_SAVE_MODEL, "training_monitor")
    if not os.path.exists(PATH_TRAING_MONITOR):
        os.makedirs(PATH_TRAING_MONITOR)

    genderType = "female"
    x_train, _, _ = readFile(genderType, "training")
    x_valid, _, _ = readFile(genderType, "validation")
    x_test, _, _ = readFile(genderType, "testing")

    genderType = "male"
    x_train, _, _ = readFile(genderType, "training", x_train)
    x_valid, _, _, = readFile(genderType, "validation", x_valid)
    x_test, _, _ = readFile(genderType, "testing", x_test)

    input_img = Input(shape=x_train.shape[1:])

    encoder = encodedModel(input_img)
    decoder = decodedModel(encoder)

    autoencoder = Model(inputs=[input_img], outputs=[decoder])
    print(autoencoder.summary())
    # Imagen summary model
    plot_model(
        autoencoder,
        to_file=os.path.join(PATH_SAVE_MODEL, "summary_model.png"),
        show_shapes=True,
    )

    # Load weight
    if args["load_weights"] != None:
        print("Loading weights from", args["load_weights"])
        autoencoder.load_weights(args["load_weights"])

    autoencoder.compile(optimizer=OPTIMIZER, loss="binary_crossentropy")

    autoencoder_train = autoencoder.fit(
        x_train,
        x_train,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        shuffle=True,
        validation_data=(x_valid, x_valid),
        callbacks=[TrainingMonitor(PATH_TRAING_MONITOR, metrics=[])],
    )

    # serialize model to YAML
    model_yaml = autoencoder.to_yaml()
    with open(os.path.join(PATH_SAVE_MODEL, "model.yaml"), "w") as yaml_file:
        yaml_file.write(model_yaml)
    # serialize weights to HDF5
    autoencoder.save_weights(os.path.join(PATH_SAVE_MODEL, "model.h5"))
    print("Saved model to disk")

    plt.style.use("ggplot")

    plt.figure()
    plt.plot(autoencoder_train.history["loss"], label="Training")
    plt.plot(autoencoder_train.history["val_loss"], label="Validation")
    plt.title("Training and validation loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend(loc="upper right")
    plt.savefig(os.path.join(PATH_SAVE_MODEL, "history_loss.png"), bbox_inches="tight")
    # plt.show()
    plt.close()

    score = autoencoder.evaluate([x_test], [x_test], batch_size=BATCH_SIZE)
    print("Test loss:", score)

    decoded_imgs = autoencoder.predict(x_test[:4], batch_size=BATCH_SIZE)

    n = 2
    plt.figure()
    for i in range(1, n + 1):
        # display original
        ax = plt.subplot(2, n, i)
        plt.imshow(x_test[i - 1])
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)

        # display reconstruction
        ax = plt.subplot(2, n, i + n)
        plt.imshow(decoded_imgs[i - 1])
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
    plt.show()
