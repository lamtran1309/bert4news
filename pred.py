import pandas as pd
import numpy as np
from transformers import BertTokenizer
import torch
from torch.utils.data import TensorDataset, DataLoader, RandomSampler, SequentialSampler

import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--model_path',default='./model_save')
parser.add_argument('--max_len',default=200,type=int)
parser.add_argument('--batch_size',default=16,type=int)
args = parser.parse_args()

# If there's a GPU available...
if torch.cuda.is_available():    

    # Tell PyTorch to use the GPU.    
    device = torch.device("cuda")

    print('There are %d GPU(s) available.' % torch.cuda.device_count())

    print('We will use the GPU:', torch.cuda.get_device_name(0))
# If not...
else:
    print('No GPU available, using the CPU instead.')
    device = torch.device("cpu")
MODEL_PATH = '../local/bert_vi/bert4news.pytorch'
# Load the dataset into a pandas dataframe.
df = pd.read_csv("./data/test.csv",sep="\t")

# Report the number of sentences.
print('Number of test sentences: {:,}\n'.format(df.shape[0]))

# Create sentence and label lists
id_test = df.id.values.tolist()
sentences = df.text.values

# Load the BERT tokenizer.
print('Loading BERT tokenizer...')
tokenizer = BertTokenizer.from_pretrained(MODEL_PATH, do_lower_case=False)

# Print the original sentence.
print(' Original: ', sentences[0])

# Print the sentence split into tokens.
print('Tokenized: ', tokenizer.tokenize(sentences[0]))

# Print the sentence mapped to token ids.
print('Token IDs: ', tokenizer.convert_tokens_to_ids(tokenizer.tokenize(sentences[0])))


# Tokenize all of the sentences and map the tokens to thier word IDs.
input_ids = []
# For every sentence...
for sent in sentences:
    try:
        if(len(sent)==0):
            sent=''
            print(sent)
    except:
        sent= ''
        print(sent)
    encoded_sent = tokenizer.encode(
                        sent,                      # Sentence to encode.
                        add_special_tokens = True, # Add '[CLS]' and '[SEP]'
                   )
    
    input_ids.append(encoded_sent)

from keras.preprocessing.sequence import pad_sequences
# Pad our input tokens
MAX_LEN = args.max_len
input_ids = pad_sequences(input_ids, maxlen=MAX_LEN, 
                          dtype="long", truncating="post", padding="post")

# Create attention masks
attention_masks = []

# Create a mask of 1s for each token followed by 0s for padding
for seq in input_ids:
  seq_mask = [float(i>0) for i in seq]
  attention_masks.append(seq_mask) 

# Convert to tensors.
prediction_inputs = torch.tensor(input_ids,dtype=torch.long)
prediction_masks = torch.tensor(attention_masks,dtype=torch.long)

# Set the batch size.  
batch_size = args.batch_size

# Create the DataLoader.
prediction_data = TensorDataset(prediction_inputs, prediction_masks)
prediction_sampler = SequentialSampler(prediction_data)
prediction_dataloader = DataLoader(prediction_data, sampler=prediction_sampler, batch_size=batch_size)

# Prediction on test set
print('Predicting labels for {:,} test sentences...'.format(len(prediction_inputs)))

# load_moel
from transformers import BertForSequenceClassification, AdamW, BertConfig
import torch.nn.functional as F
import os
MODEL_PATH = args.model_path

list_model = os.listdir(MODEL_PATH)
list_predictions = []
for model_name in list_model:
    model = BertForSequenceClassification.from_pretrained(
        os.path.join(MODEL_PATH,model_name),
        num_labels = 2,
        output_attentions = False,
        output_hidden_states = False
    )
    if torch.cuda.is_available():
        model.cuda()
    model.eval()

    # Tracking variables 
    predictions= []
    # Predict 
    for batch in prediction_dataloader:
        batch = tuple(t.to(device) for t in batch)
        b_input_ids, b_input_mask = batch
        with torch.no_grad():
            outputs = model(b_input_ids, token_type_ids=None, 
                            attention_mask=b_input_mask)

        logits = outputs[0]
        logits = F.softmax(logits,dim=1)
        logits = logits.detach().cpu().numpy()  
        predictions.append(logits)
    flat_predictions = [item for sublist in predictions for item in sublist]
    list_predictions.append(flat_predictions)

list_predictions = np.asarray(list_predictions)

list_predictions = np.mean(list_predictions,axis=0)

fw = open("submission.csv","w",encoding="utf-8")
fw.write("id,label")
fw.write("\n")
flat_predictions = np.argmax(list_predictions, axis=1).flatten().tolist()
for i in range(len(id_test)):
    fw.write(",".join([id_test[i],str(flat_predictions[i])]))
    fw.write('\n')
fw.close()