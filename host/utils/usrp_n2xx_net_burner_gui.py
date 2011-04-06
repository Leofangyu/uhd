#!/usr/bin/env python
#
# Copyright 2011 Ettus Research LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import threading
import usrp_n2xx_net_burner #import implementation
try:
    import tkinter, tkinter.filedialog, tkinter.font, tkinter.messagebox
except ImportError:
    import tkFileDialog, tkFont, tkMessageBox
    import Tkinter as tkinter
    tkinter.filedialog = tkFileDialog
    tkinter.font = tkFont
    tkinter.messagebox = tkMessageBox
import os

class BinFileEntry(tkinter.Frame):
    """
    Simple file entry widget for getting the file path of bin files.
    Combines a label, entry, and button with file dialog callback.
    """

    def __init__(self, root, what, def_path=''):
        self._what = what
        tkinter.Frame.__init__(self, root)
        tkinter.Label(self, text=what+":").pack(side=tkinter.LEFT)
        self._entry = tkinter.Entry(self, width=50)
        self._entry.insert(tkinter.END, def_path)
        self._entry.pack(side=tkinter.LEFT)
        tkinter.Button(self, text="...", command=self._button_cb).pack(side=tkinter.LEFT)

    def _button_cb(self):
        filename = tkinter.filedialog.askopenfilename(
            parent=self,
            filetypes=[('bin files', '*.bin'), ('all files', '*.*')],
            title="Select bin file for %s"%self._what,
            initialdir=os.path.dirname(self.get_filename()),
        )

        # open file on your own
        if filename:
            self._entry.delete(0, tkinter.END)
            self._entry.insert(0, filename)

    def get_filename(self):
        return self._entry.get()

class ProgressBar(tkinter.Canvas):
    """
    A simple implementation of a progress bar.
    Draws rectangle that fills from left to right.
    """

    def __init__(self, root, width=500, height=20):
        self._width = width
        self._height = height
        tkinter.Canvas.__init__(self, root, relief="sunken", borderwidth=2, width=self._width-2, height=self._height-2)
        self._last_fill_pixels = None
        self.set(0.0)

    def set(self, frac):
        """
        Update the progress where fraction is between 0.0 and 1.0
        """
        #determine the number of pixels to draw
        fill_pixels = int(round(self._width*frac))
        if fill_pixels == self._last_fill_pixels: return
        self._last_fill_pixels = fill_pixels

        #draw a rectangle representing the progress
        if frac: self.create_rectangle(0, 0, fill_pixels, self._height, fill="#357EC7")
        else:    self.create_rectangle(0, 0, self._width, self._height, fill="#E8E8E8")

class SectionLabel(tkinter.Label):
    """
    Make a text label with bold font.
    """

    def __init__(self, root, text):
        tkinter.Label.__init__(self, root, text=text)

        #set the font bold
        f = tkinter.font.Font(font=self['font'])
        f['weight'] = 'bold'
        self['font'] = f.name

class USRPN2XXNetBurnerApp(tkinter.Frame):
    """
    The top level gui application for the usrp-n2xx network burner.
    Creates entry widgets and button with callback to write images.
    """

    def __init__(self, root, addr, fw, fpga):

        tkinter.Frame.__init__(self, root)

        #pack the file entry widgets
        SectionLabel(self, text="Select Images").pack(pady=5)
        self._fw_img_entry = BinFileEntry(self, "Firmware Image", def_path=fw)
        self._fw_img_entry.pack()
        self._fpga_img_entry = BinFileEntry(self, "FPGA Image", def_path=fpga)
        self._fpga_img_entry.pack()

        #pack the destination entry widget
        SectionLabel(self, text="Select Address").pack(pady=5)
        self._addr_entry = tkinter.Entry(self, width=30)
        self._addr_entry.insert(tkinter.END, addr)
        self._addr_entry.pack()

        #the do it button
        SectionLabel(self, text="").pack(pady=5)
        button = tkinter.Button(self, text="Burn Images", command=self._burn)
        self._enable_input = lambda: button.configure(state=tkinter.NORMAL)
        self._disable_input = lambda: button.configure(state=tkinter.DISABLED)
        button.pack()

        #a progress bar to monitor the status
        progress_frame = tkinter.Frame(self)
        progress_frame.pack()
        self._status = tkinter.StringVar()
        tkinter.Label(progress_frame, textvariable=self._status).pack(side=tkinter.LEFT)
        self._pbar = ProgressBar(progress_frame)
        self._pbar.pack(side=tkinter.RIGHT, expand=True)

    def _burn(self):
        self._disable_input()
        threading.Thread(target=self._burn_bg).start()

    def _burn_bg(self):
        #grab strings from the gui
        fw = self._fw_img_entry.get_filename()
        fpga = self._fpga_img_entry.get_filename()
        addr = self._addr_entry.get()

        #check input
        if not addr:
            tkinter.messagebox.showerror('Error:', 'No address specified!')
            return
        if not fw and not fpga:
            tkinter.messagebox.showerror('Error:', 'No images specified!')
            return
        if fw and not os.path.exists(fw):
            tkinter.messagebox.showerror('Error:', 'Firmware image not found!')
            return
        if fpga and not os.path.exists(fpga):
            tkinter.messagebox.showerror('Error:', 'FPGA image not found!')
            return

        try:
            #make a new burner object and attempt the burner operation
            burner = usrp_n2xx_net_burner.burner_socket(addr=addr)

            for (image_type, fw_img, fpga_img) in (('FPGA', '', fpga), ('Firmware', fw, '')):
                #setup callbacks that update the gui
                def status_cb(status):
                    self._pbar.set(0.0) #status change, reset the progress
                    self._status.set("%s %s "%(status.title(), image_type))
                burner.set_callbacks(progress_cb=self._pbar.set, status_cb=status_cb)
                burner.burn_fw(fw=fw_img, fpga=fpga_img, reset=False, safe=False)

            if tkinter.messagebox.askyesno("Burn was successful!", "Reset the device?"):
                burner.reset_usrp()

        except Exception as e:
            tkinter.messagebox.showerror('Verbose:', 'Error: %s'%str(e))

        #reset the progress bar
        self._pbar.set(0.0)
        self._status.set("")
        self._enable_input()

########################################################################
# main
########################################################################
if __name__=='__main__':
    options = usrp_n2xx_net_burner.get_options()
    root = tkinter.Tk()
    root.title('USRP-N2XX Net Burner')
    USRPN2XXNetBurnerApp(root, addr=options.addr, fw=options.fw, fpga=options.fpga).pack()
    root.mainloop()
    exit()
