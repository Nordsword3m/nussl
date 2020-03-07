import pytest
from nussl.datasets import BaseDataset, transforms
from nussl.datasets.base_dataset import DataSetException
import nussl
from nussl import STFTParams
import numpy as np
import soundfile as sf
import itertools

class BadTransform(object):
    def __init__(self, fake=None):
        self.fake = fake

    def __call__(self, data):
        return 'not a dictionary'

class BadDataset(BaseDataset):
    def get_items(self, folder):
        return {'anything': 'not a list'}
    
    def process_item(self, item):
        return 'not a dictionary'

def dummy_process_item(self, item):
    audio = self._load_audio_file(item)
    output = {
        'mix': audio,
        'sources': {'key': audio}
    }
    return output

def dummy_process_item_by_audio(self, item):
    data, sr = sf.read(item)
    audio = self._load_audio_from_array(data, sr)
    output = {
        'mix': audio,
        'sources': {'key': audio}
    }
    return output

def initialize_bad_dataset_and_run():
    _bad_transform = BadTransform()
    _bad_dataset = BadDataset('test', transform=_bad_transform)
    _bad_dataset[0]
    

def test_dataset_base(benchmark_audio, monkeypatch):
    keys = [benchmark_audio[k] for k in benchmark_audio]  
    def dummy_get(self, folder):
        return keys      

    pytest.raises(DataSetException, initialize_bad_dataset_and_run)

    monkeypatch.setattr(BadDataset, 'get_items', dummy_get)
    pytest.raises(DataSetException, initialize_bad_dataset_and_run)

    monkeypatch.setattr(BadDataset, 'process_item', dummy_process_item)
    pytest.raises(transforms.TransformException, initialize_bad_dataset_and_run)

    monkeypatch.setattr(BaseDataset, 'get_items', dummy_get)
    monkeypatch.setattr(BaseDataset, 'process_item', dummy_process_item)

    _dataset = BaseDataset('test')

    assert len(_dataset) == len(keys)

    audio_signal = nussl.AudioSignal(keys[0])
    assert _dataset[0]['mix'] == audio_signal

    _dataset = BaseDataset('test', transform=BadTransform())
    pytest.raises(transforms.TransformException, _dataset.__getitem__, 0) 

    psa = transforms.MagnitudeSpectrumApproximation()
    _dataset = BaseDataset('test', transform=psa)

    output = _dataset[0]
    assert 'source_magnitudes' in output
    assert 'mix_magnitude' in output
    assert 'ideal_binary_mask' in output

    monkeypatch.setattr(
        BaseDataset, 'process_item', dummy_process_item_by_audio)
    psa = transforms.MagnitudeSpectrumApproximation()
    _dataset = BaseDataset('test', transform=psa)

    output = _dataset[0]
    assert 'source_magnitudes' in output
    assert 'mix_magnitude' in output
    assert 'ideal_binary_mask' in output

def test_dataset_base_audio_signal_params(benchmark_audio, monkeypatch):
    keys = [benchmark_audio[k] for k in benchmark_audio]  
    def dummy_get(self, folder):
        return keys      

    monkeypatch.setattr(BaseDataset, 'get_items', dummy_get)

    monkeypatch.setattr(
        BaseDataset, 'process_item', dummy_process_item_by_audio)

    stft_params = [
        STFTParams(
            window_length=256,
            hop_length=32,
            window_type='triang'), 
        None
    ]

    sample_rates = [4000, None]
    num_channels = [1, 2, None]
    strict_sample_rate = [False, True]

    product = itertools.product(
        stft_params, sample_rates, num_channels, strict_sample_rate)

    def _get_outputs(dset):
        outputs = []
        for i in range(len(dset)):
            outputs.append(dset[i])
        return outputs


    for s, sr, nc, s_sr in product:
        _dataset = BaseDataset(
            'test', stft_params=s, 
            sample_rate=sr, num_channels=nc,
            strict_sample_rate=s_sr)
        
        if s_sr and sr is not None:
            pytest.raises(DataSetException, _get_outputs, _dataset)
            continue

        outputs = _get_outputs(_dataset)

        # they should all have the same sample rate and stft
        _srs = []
        _stfts = []

        for i, o in enumerate(outputs):
            if sr:
                assert o['mix'].sample_rate == sr
            if s:
                assert o['mix'].stft_params == s
            if nc:
                if o['mix'].num_channels < nc:
                    assert pytest.warns(UserWarning, _dataset.__getitem__, i)
                else:
                    assert o['mix'].num_channels == nc
            _srs.append(o['mix'].sample_rate)
            _stfts.append(o['mix'].stft_params)

        for _sr, _stft in zip(_srs, _stfts):
            assert _sr == _srs[0]
            assert _stft == _stfts[0]