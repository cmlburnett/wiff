"""
WIFF is the primary class that the application interacts with.
It contains the big functions like open() and new() as well as add_annotation() and add_frames().
All operations manipulating a WIFF recording should ultimately be done through a function in this object.

The actual mmap()'ing files is done through the _filewrap class and is the single point of data read/write
 for ALL files in this recording.

Wiff_chunk handles the 24-byte header on each chunk.
WIFFINFO, WIFFWAVE, and WIFFANNO are the front ends for the major chunk types.
"""

import datetime
import bstruct
import json

import os.path

from .util import _filewrap, twotuplecheck, DATE_FMT
from .wiffchunk import WIFF_chunk
from .wiffanno import WIFFANNO
from .wiffinfo import WIFFINFO
from .wiffwave import WIFFWAVE

class WIFF:
	"""
	Primary interface class to a WIFF recording.
	All interactions should occur through this class.
	Supply the primary WIFF file that contains the information for the recording
	If creating a new file, properties in @props is needed to start the recording.

	"""
	def __init__(self):
		"""
		Create a empty WIFF object.
		Call open() or new() to open an existing WIFF file or to create a new one, respectively.
		This is not meant to be called directly.
		"""

		self._files = {}
		self._chunks = {}

		self._current_file = None
		self._current_segment = None
		self._current_annotations = None

	@classmethod
	def open(cls, fname):
		"""
		Open an existing WIFF file.
		"""
		w = cls()

		# Blank all files
		w._fname = fname
		w._files.clear()
		w._chunks.clear()
		w._chunks[fname] = []

		# Wrap file
		f = w._files[fname] = _filewrap(fname)

		chunks = WIFF_chunk.FindChunks(f.f)
		for chunk in chunks:
			c = WIFF_chunk(f, chunk['offset header'])
			if chunk['magic'] == 'WIFFINFO':
				wi = WIFFINFO(w, f, c)
				w._chunks[fname].append(wi)

				if 'INFO' in w._chunks:
					raise NotImplementedError("Multiple WAVEINFO chunks is not supported")
				w._chunks['INFO'] = wi
			elif chunk['magic'] == 'WIFFWAVE':
				ww = WIFFWAVE(w, f, c)
				ww.setup()
				w._chunks[fname].append(ww)
			elif chunk['magic'] == 'WIFFANNO':
				wa = WIFFANNO(self, f, c)
				w._chunks[fname].append(wa)

			else:
				raise TypeError('Uknown chunk magic: %s' % chunk['magic'])

		return w

	@classmethod
	def new(cls, fname, props, force):
		"""
		@props -- dictionary including:
			'start'			datetime objects
			'end'			datetime objects
			'description'	string describing the recording
			'fs'			sampling frequency (int)
			'channels'		list of channels
				'name'			name of the channel
				'bit'			bits (int) of each measurement
				'unit'			physical units of the measurement (str)
				'comment'		Arbitrary comment on the channel
			'files'			list of files, probably empty (except for INFO file) for a new recording
		"""

		if os.path.exists(fname):
			if not force:
				raise Exception("File '%s' exists, cannot open; pass force=True to override" % fname)

			# Have to open it to find all the files linked with it to completely delete it
			files = None
			try:
				w = cls.open(fname)
				files = [f.name.val for f in w.files]
				w.close()
			except Exception as e:
				pass

			if files is None:
				# Likely this isn't a WIFF file so delete just it
				os.unlink(fname)
			else:
				# Unlink all files, if they are present
				for f in files:
					if os.path.exists(f):
						os.unlink(f)

		# Make a shell object
		w = cls()

		# Blank all files
		w._fname = fname
		w._chunks[fname] = []

		# Wrap file
		f = w._files[fname] = _filewrap(fname)
		# Initial 4096 block
		f.resize(4096)

		c = WIFF_chunk(f, 0)

		# No frames yet
		num_frames = 0

		props['files'].append({
			'name': fname,
			'fidx_start': 0,
			'fidx_end': 0,
			'aidx_start': 0,
			'aidx_end': 0,
		})

		c = WIFF_chunk(f, 0)
		wi = WIFFINFO(w, f, c)
		wi.initchunk()
		wi.initheader(props['start'], props['end'], props['description'], props['fs'], 0,0, props['channels'], props['files'])


		w._chunks[fname] = [wi]
		w._chunks['INFO'] = wi

		return w

	@property
	def fs(self): return self._chunks['INFO'].fs
	@fs.setter
	def fs(self, v): self._chunks['INFO'].fs = v

	@property
	def start(self): return self._chunks['INFO'].start
	@start.setter
	def start(self, v): self._chunks['INFO'].start = v

	@property
	def end(self): return self._chunks['INFO'].end
	@end.setter
	def end(self, v): self._chunks['INFO'].end = v

	@property
	def description(self): return self._chunks['INFO'].description
	@description.setter
	def description(self, v): self._chunks['INFO'].description = v

	@property
	def num_channels(self): return self._chunks['INFO'].num_channels
	@num_channels.setter
	def num_channels(self, v): self._chunks['INFO'].num_channels = v

	@property
	def num_files(self): return self._chunks['INFO'].num_files
	@num_files.setter
	def num_files(self, v): self._chunks['INFO'].num_files = v

	@property
	def num_frames(self): return self._chunks['INFO'].num_frames
	@num_frames.setter
	def num_frames(self, v): self._chunks['INFO'].num_frames = v

	@property
	def num_annotations(self): return self._chunks['INFO'].num_annotations
	@num_annotations.setter
	def num_annotations(self, v): self._chunks['INFO'].num_annotations = v

	@property
	def channels(self): return self._chunks['INFO'].channels

	@property
	def files(self): return self._chunks['INFO'].files

	@property
	def current_segment(self): return self._current_segment

	def __enter__(self):
		pass
	def __exit__(self, *exc):
		self.close()
		return False

	def close(self):
		for fname,o in self._files.items():
			try:
				o.close()
			except Exception as e:
				print(e)

	# Get all matching chunks
	def _GetINFO(self, fname=None): return self._GetChunks('WIFFINFO', fname=fname)
	def _GetWAVE(self, fname=None): return self._GetChunks('WIFFWAVE', fname=fname)
	def _GetANNO(self, fname=None): return self._GetChunks('WIFFANNO', fname=fname)
	def _GetChunks(self, magic=None, fname=None):
		"""
		Find all matching chunks for the magic (WIFFINFO, WIFFWAVE, WIFFANNO) or use a _GetINFO, _GetWAVE, _GetANNO.
		Can supply filename @fname to limit chunk search.
		"""
		# Coerce to a list
		if isinstance(fname, str):
			fname = [fname]
		else:
			# Assume it's ok otherwise
			pass

		if magic == 'WIFFINFO':
			# Doesn't matter what fname is for the info, it's always in the main file
			yield self._chunks['INFO']
		else:
			# Iterate over all files
			for key in self._chunks.keys():
				if key == 'INFO': continue
				if fname is not None:
					if key not in fname: continue

				# Iterate over the chunks in each file
				chunks = self._chunks[key]
				for chunk in chunks:
					# Compare magic
					if magic is None:
						yield chunk
					elif chunk.magic == magic:
						yield chunk

	def get_annotations(self, typ=None, fidx=None, fname=None):
		"""
		Get all annotations that match all supplied arguments.
		@typ -- Type of the annotation must match exactly
		@fidx -- Frame index must be between the start and stop indices of the annotation
		@fname -- File name (string or list of strings) to limit annotation search to

		These options can take the appropriate type (string, int, etc).
		Alternatively, the value can be a function whose value is evaluated as a boolean.
		"""

		# Create filter functions based on arguments
		filts = []
		if typ is not None:
			if isinstance(typ, str):
				filts.append(lambda x: x.type.val == typ)
			elif isinstance(typ, types.FunctionType):
				filts.append(typ)
			else:
				raise TypeError('Unrecognize type for @typ argument (expect str or function): "%s"' % (str(typ),))

		if fidx is not None:
			if isinstance(fidx, int):
				filts.append(lambda x,fidx=fidx: x.fidx_start.val <= fidx and x.fidx_end.val >= fidx)
			elif isinstance(fidx, types.FunctionType):
				filts.append(fidx)
			elif isinstance(fidx, bstruct.interval):
				filts.append(lambda x, fidx=fidx: x.fidx_start.val in fidx or x.fidx_end.val in fidx)
			else:
				raise TypeError('Unrecognize type for @fidx argument (expect int or function): "%s"' % (str(fidx),))

		# If no filters provided as arguments, accept everything
		if not len(filts):
			filts.append(lambda x:True)

		# Iterate over all annotation chunks
		chunks = self._GetANNO(fname=fname)
		for annos in chunks:
			# Iterate over all annotations
			for ann in annos.annotations:
				# Apply filters and accept if all are True
				if all([_(ann) for _ in filts]):
					yield ann

	def get_frames(self, val, to_int=True):
		ret = {
			'start': None,
			'stop': None,
			'frames': None,
		}
		if isinstance(val, bstruct.interval):
			ret['start'] = val.start
			ret['stop'] = val.stop
			ret['interval'] = val
		elif isinstance(val, tuple):
			val = twotuplecheck(val)
			ret['start'] = val.start
			ret['stop'] = val.stop
			ret['interval'] = val
		else:
			raise TypeError("Unrecognized val type: %s" % (type(val),))

		ret['frames'] = list(self.iter_frames(val, to_int=to_int))
		ret['stop'] = ret['start'] + len(ret['frames']) - 1

		return ret

	def get_frame(self, index, to_int=True):
		"""
		Get a single frame of data as bytes (@to_int == False) or integers (@to_int == True).
		Not very efficient for repeated use.
		"""
		chunks = self._GetWAVE()
		for chunk in chunks:
			if chunk.fidx_start > index:
				continue
			if chunk.fidx_end < index:
				continue

			# index is in this chunk
			off = index - chunk.fidx_start

			if to_int:
				bs = chunk[off]
				return chunk.DeSer(bs)
			else:
				return chunk[off]

		raise KeyError("Frame index %d not found" % index)

	def iter_frames(self, val, to_int=True):
		"""
		Gets frames in sequence from @val frame indices.
		Get frames of data as bytes (@to_int == False) or integers (@to_int == True).
		"""

		# Get chunks and sort by start
		chunks = self._GetWAVE()
		chunks = sorted(chunks, key=lambda x:x.fidx_start)

		val = twotuplecheck(val)

		i = val.start

		for chunk in chunks:
			# Skip to first chunk
			if chunk.fidx_start > i:
				continue

			while i < chunk.fidx_end:
				# Get relative offset in the chunk and get frame
				off = i - chunk.fidx_start
				bs = chunk[off]

				if to_int:
					yield chunk.DeSer(bs)
				else:
					yield bs

				i += 1
				if i > val.stop:
					raise StopIteration


	# -----------------------------------------------
	# -----------------------------------------------
	# Add data

	def set_file(self, fname):
		"""
		Change the current segment
		"""
		self._current_file = self._files[fname]
		self._current_segment = None

		return self._current_file

	def set_segment(self, segment):
		"""
		Change the current segment
		"""
		if isinstance(segment, int):
			raise NotImplementedError
		elif isinstance(segment, WIFFWAVE):
			self._current_file = segment.fw
			self._current_segment = segment
		else:
			raise NotImplementedError

		return self._current_segment

	def new_file(self, fname, force=False):
		"""
		Start a new file without any segments
		"""
		if fname in self._files:
			raise Exception("File '%s' is already associated with this WIFF file, cannot create it" % fname)

		if os.path.exists(fname):
			if not force:
				raise Exception("File '%s' exists, cannot open; pass force=True to override" % fname)

			# Truncate file
			os.truncate(fname, 0)

		# Add file
		f = self._files[fname] = _filewrap(fname)
		self._chunks[fname] = []
		self.set_file(fname)

		fidx_start = fidx_end = self.num_frames
		aidx_start = aidx_end = self.num_annotations

		# Add file to INFO chunk
		self._chunks['INFO'].add_file(fname, fidx_start, fidx_end, aidx_start, aidx_end)

	def new_annotations(self):
		"""
		Start a new chunk for annotations.
		"""

		if self._current_file is None:
			raise ValueError("Must set active file before creating a new annotations chunk")

		# Blank current annotations pointer
		self._current_annotations = None

		# Get last chunk
		fname = self._current_file.fname
		cs = self._chunks[fname]
		if len(cs):
			lastchunk = cs[-1].chunk

			# End of the last chunk (offset + size) is where the next block begins
			nextoff = lastchunk.offset + lastchunk.size


			# Create new chunk
			self._current_file.resize_add(4096)
			c = WIFF_chunk(self._current_file, nextoff)
		else:
			# No chunks, this starts at the beginning of the file
			c = WIFF_chunk(self._current_file, 0)

		w = WIFFANNO(self, self._current_file, c)
		cs.append(w)
		w.initchunk(None)
		w.initheader()

		self._current_annotations = w

	def new_segment(self, chans, segmentid=None):
		"""
		Start a new segment in the current file
		"""

		if self._current_file is None:
			raise ValueError("Must set active file before creating a new segment")

		# Blank current segment pointer
		self._current_segment = None

		# Auto-generated segment ID's
		if segmentid is None:
			raise NotImplementedError("Pick an available segmentid")

		# Get last chunk
		fname = self._current_file.fname
		cs = self._chunks[fname]
		if len(cs) == 0:
			firstsegment = True

			# No chunks yet (shouldn't happen on main file, but can happen just after new_file)
			c = WIFF_chunk(self._current_file, 0)
		else:
			firstsegment = False

			lastchunk = cs[-1].chunk

			# End of the last chunk (offset + size) is where the next block begins
			nextoff = lastchunk.offset + lastchunk.size

			# Create new chunk
			c = WIFF_chunk(self._current_file, nextoff)

		# Create chunk data
		if not firstsegment:
			# Have to create a file with some contents in order to mmap it, so use this first page if first segment
			self._current_file.resize_add(4096)

		w = WIFFWAVE(self, self._current_file, c)
		cs.append(w)
		w.initchunk(None, segmentid)

		# Create WAVE header
		w.initheader(chans, self.num_frames, self.num_frames)

		# Current segment
		self._current_segment = w

		return w

	def add_frames(self, *frames):
		"""
		Add frames of samples to the current segment
		"""
		return self._current_segment.add_frames(*frames)

	def add_frame(self, *samps):
		"""
		Add a frame of samples to the current segment
		"""
		if self._current_segment is None:
			raise ValueError("Cannot add frames, must create or set an segment chunk")
		return self._current_segment.add_frame(*samps)

	def add_annotation(self, **kargs):
		"""
		Add an annotation to the current chunk.
		"""
		if self._current_annotations is None:
			raise ValueError("Cannot add annotations, must create or set an annotations chunk")
		return self._current_annotations.add_annotation(**kargs)

	# -----------------------------------------------
	# -----------------------------------------------
	# Dump

	def dumps_dict(self):
		"""
		Dump WIFF meta data into a dict() for handling within Python.
		"""
		ret = {
			'file': self._fname,
			'start': self.start,
			'end': self.end,
			'description': self.description,
			'fs': self.fs,
			'num_frames': self.num_frames,
			'num_annotations': self.num_annotations,
			'num_channels': self.num_channels,
			'num_files': self.num_files,
			'channels': [],
			'files': [],
			'segments': [],
		}

		for i in range(self.num_channels):
			c = self.channels[i]
			ret['channels'].append({
				'idx': c.index.val,
				'name': c.name.val,
				'bit': c.bit.val,
				'unit': c.unit.val,
				'comment': c.comment.val,
			})
		for i in range(self.num_files):
			f = self.files[i]
			ret['files'].append({
				'idx': f.index.val,
				'name': f.name.val,
				'fidx start': f.fidx_start.val,
				'fidx end': f.fidx_end.val,
				'aidx start': f.aidx_start.val,
				'aidx end': f.aidx_end.val,
			})

		return ret

	def dumps_str(self):
		"""
		Dump WIFF meta data into a string that can be printed.
		"""

		d = self.dumps_dict()

		ret = []
		ret.append("%30s | %s" % ("File", d['file']))
		ret.append("%30s | %s" % ("Description", d['description']))
		ret.append("%30s | %s" % ("Start", d['start']))
		ret.append("%30s | %s" % ("End", d['end']))
		ret.append("%30s | %s" % ("fs", d['fs']))
		ret.append("%30s | %s" % ("Number of Frames", d['num_frames']))
		ret.append("%30s | %s" % ("Number of Annotations", d['num_annotations']))
		ret.append("%30s | %s" % ("Number of Channels", d['num_channels']))
		ret.append("%30s | %s" % ("Number of Files", d['num_files']))
		ret.append("")
		for c in d['channels']:
			ret.append("%30s %d" % ('Channel', c['idx']))
			ret.append("%35s | %s" % ('Name', c['name']))
			ret.append("%35s | %s" % ('Bit', c['bit']))
			ret.append("%35s | %s" % ('Unit', c['unit']))
			ret.append("%35s | %s" % ('Comment', c['comment']))
		ret.append("")
		for f in d['files']:
			ret.append("%30s %d" % ('File', f['idx']))
			ret.append("%35s | %s" % ('Name', f['name']))
			ret.append("%35s | %s" % ('Frame Index Start', f['fidx start']))
			ret.append("%35s | %s" % ('Frame Index End', f['fidx end']))
			ret.append("%35s | %s" % ('Annotation Index Start', f['aidx start']))
			ret.append("%35s | %s" % ('Annotation Index End', f['aidx end']))

		return "\n".join(ret)

	def dumps_json(self):
		"""
		Dump WIFF meta data into a json for handling within Python.
		"""

		def dtconv(o):
			if isinstance(o, datetime.datetime):
				return o.strftime(DATE_FMT)

		return json.dumps(self.dumps_dict(), default=dtconv)

