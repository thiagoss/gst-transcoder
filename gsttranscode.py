#!/usr/bin/python
# -*- coding: utf-8 -*-

# gst-transcoder.py
# Copyright (C) 2012 Thiago Santos <thiago.sousa.santos@collabora.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA 02110-1301, USA.

import sys
import argparse

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstPbutils", "1.0")

from gi.repository import GObject, Gst, GstPbutils

GObject.threads_init()
Gst.init(None)

def create_webm_profile():
    webmcaps = Gst.Caps.new_empty_simple('video/webm')
    vp8caps = Gst.Caps.new_empty_simple('video/x-vp8')
    vorbiscaps = Gst.Caps.new_empty_simple('audio/x-vorbis')

    container = GstPbutils.EncodingContainerProfile.new('webm', None, webmcaps, None)
    video = GstPbutils.EncodingVideoProfile.new(vp8caps, None, None, 0)
    audio = GstPbutils.EncodingAudioProfile.new(vorbiscaps, None, None, 0)
    container.add_profile(video)
    container.add_profile(audio)
    return container

class Transcoder(GObject.GObject):
    """


       Signals:
       eos - Signal emited when the transcoder has successfully finished processing
       error - Signal emited when the transcoder has finished because it found an error
       progress - Signal emited periodically to inform about the progress of the transcoding
       started - Signal emited when transcoding starts
    """

    __gsignals__ = {'eos': (GObject.SignalFlags.RUN_LAST,
                            GObject.TYPE_NONE,
                            ()),
                    'error': (GObject.SignalFlags.RUN_LAST,
                              GObject.TYPE_NONE,
                              (GObject.TYPE_STRING, GObject.TYPE_STRING)),
                    'progress': (GObject.SignalFlags.RUN_LAST,
                                 GObject.TYPE_NONE,
                                 (GObject.TYPE_FLOAT,)),
                    'started': (GObject.SignalFlags.RUN_LAST,
                                GObject.TYPE_NONE,
                                ()),
                   }
    def eos(self):
        pass
    def error(self, error_message, debug_message):
        pass
    def progress(self, progress):
        pass
    def started(self):
        pass

    def __init__(self):
        super(Transcoder, self).__init__()
        self.pipeline = Gst.Pipeline()
        self.filesink = Gst.ElementFactory.make('filesink', None)
        self.encodebin = Gst.ElementFactory.make('encodebin', None)
        self.decodebin = Gst.ElementFactory.make('decodebin', None)
        self.progressreport = Gst.ElementFactory.make('progressreport', None)
        self.filesrc = Gst.ElementFactory.make('filesrc', None)

        self.pipeline.add(self.filesrc)
        self.pipeline.add(self.progressreport)
        self.pipeline.add(self.decodebin)
        self.pipeline.add(self.encodebin)
        self.pipeline.add(self.filesink)

        self.filesrc.link(self.progressreport)
        self.progressreport.link(self.decodebin)
        self.encodebin.link(self.filesink)

        self.decodebin.connect('pad-added', self._decodebin_pad_added)

        bus = self.pipeline.get_bus()
        self.bus_watch_id = bus.add_watch(0, self._bus_message_handler, None)

    def set_source_location(self, location):
        self.filesrc.set_property('location', location)

    def set_destination_location(self, location):
        self.filesink.set_property('location', location)

    def set_encoding_profile(self, profile):
        self.encodebin.set_property('profile', profile)

    def start(self):
        self.emit('started')
        ret = t.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            self.emit("error", "Failed to start", None)

    def stop(self):
        __,st,__ = t.pipeline.get_state(0)
        self._do_stop()
        if st in [Gst.State.PLAYING, Gst.State.PAUSED]:
            self.emit("error", 'Aborted', None)

    def _do_stop(self):
        t.pipeline.set_state(Gst.State.NULL)

    def _bus_message_handler(self, bus, message, udata=None):
        t = message.type
        if t == Gst.MessageType.EOS:
            self._do_stop()
            self.emit('eos')
        elif t == Gst.MessageType.ERROR:
            self._do_stop()
            err,debug = message.parse_error()
            self.emit('error', err.message, debug)
        elif t == Gst.MessageType.ELEMENT:
            if message.get_structure().get_name() == 'progress':
                found,perc = message.get_structure().get_double('percent-double')
                if found:
                    self.emit('progress', perc)
        return True

    def _decodebin_pad_added(self, decodebin, pad, udata=None):
        caps = pad.query_caps(None)
	if not caps:
	    print 'pad with no caps ignored'
	    return

        queue = Gst.ElementFactory.make('queue', None)

        encpad = None

        if caps.get_structure(0).get_name().startswith('video'):
            encpad = self.encodebin.get_request_pad('video_%u')
        elif caps.get_structure(0).get_name().startswith('audio'):
            encpad = self.encodebin.get_request_pad('audio_%u')
        else:
            print 'ignoring unknown stream, %s' % caps.to_string()
            return

	if not encpad:
            print "Couldn't create encoding pad for %s" % caps.to_string()
            return

        self.pipeline.add(queue)
        pad.link(queue.get_static_pad('sink'))
        queue.get_static_pad('src').link(encpad)
        queue.sync_state_with_parent()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='GStreamer Transcoder')
    parser.add_argument('--source', type=str,
                        help='The source file location')
    parser.add_argument('--destination', type=str,
                        help='The destination file location')

    args = parser.parse_args()
    if not args.source:
        print 'no source location supplied'
        sys.exit(-1)
    if not args.destination:
        print 'no destination location supplied'
        sys.exit(-1)

    t = Transcoder()
    t.set_destination_location(args.destination)
    t.set_encoding_profile(create_webm_profile())
    t.set_source_location(args.source)
    t.start()
    loop = GObject.MainLoop()
    loop.run()

