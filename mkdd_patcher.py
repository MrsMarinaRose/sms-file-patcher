#!/usr/bin/env python
import configparser
import importlib
import os
import platform
import signal
import textwrap

import customtkinter

from PIL import Image, ImageTk

from src import CTkToolTip

patcher_gui = importlib.import_module('patcher-gui')

ICON_RESOLUTIONS = (16, 24, 32, 48, 64, 128, 256)


class MKDDPatcherApp(customtkinter.CTk):

    def __init__(self):
        super().__init__()

        config = self._get_config()

        self._last_input_iso = ''
        self._last_input_iso_picked = ''
        self._last_output_iso = ''
        self._last_output_iso_picked = ''
        self._last_custom_tracks = ''
        self._last_custom_tracks_picked = ''

        if 'paths' in config:
            self._last_input_iso = config['paths'].get('input_iso', '')
            self._last_input_iso_picked = config['paths'].get('input_iso_picked', '')
            self._last_output_iso = config['paths'].get('output_iso', '')
            self._last_output_iso_picked = config['paths'].get('output_iso_picked', '')
            self._last_custom_tracks = config['paths'].get('custom_tracks', '')
            self._last_custom_tracks_picked = config['paths'].get('custom_tracks_picked', '')

        self.title('MKDD Patcher')
        if platform.system() == 'Windows':
            self.iconbitmap(get_ico_path('logo'))
        else:
            logo = ImageTk.PhotoImage(file=get_icon_path('logo', ICON_RESOLUTIONS[-1]))
            self.iconphoto(False, logo)

        font_width, font_height = get_font_metrics()
        padding = int(font_width * 1.75)
        spacing = int(font_width * 0.75)

        if config.has_option('geometry', 'window'):
            self.geometry(config['geometry']['window'])
        else:
            self.geometry(f'{font_width * 100}x{font_height * 20}')
        self.minsize(font_width * 50, font_height * 12)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure((0, 1), weight=1)

        main_frame = customtkinter.CTkFrame(master=self, fg_color='transparent')
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid(row=0,
                        column=0,
                        columnspan=2,
                        padx=padding,
                        pady=(padding, 0),
                        sticky='nsew')

        input_iso_label = customtkinter.CTkLabel(master=main_frame, text='Input ISO')
        input_iso_label.grid(row=0, column=0, padx=(0, spacing), pady=(0, spacing), sticky='nse')
        output_iso_label = customtkinter.CTkLabel(master=main_frame, text='Output ISO')
        output_iso_label.grid(row=1, column=0, padx=(0, spacing), pady=(0, spacing), sticky='nse')
        custom_tracks_label = customtkinter.CTkLabel(master=main_frame, text='Custom Tracks / Mods')
        custom_tracks_label.grid(row=2, column=0, padx=(0, spacing), pady=0, sticky='ne')

        self.input_iso_entry = customtkinter.CTkEntry(master=main_frame)
        self.input_iso_entry.grid(row=0, column=1, padx=0, pady=(0, spacing), sticky='nesw')
        self.output_iso_entry = customtkinter.CTkEntry(master=main_frame)
        self.output_iso_entry.grid(row=1, column=1, padx=0, pady=(0, spacing), sticky='nesw')
        self.custom_tracks_box = customtkinter.CTkTextbox(master=main_frame, wrap='none')
        self.custom_tracks_box.grid(row=2, column=1, padx=0, pady=0, sticky='nesw')

        input_iso_button = customtkinter.CTkButton(master=main_frame,
                                                   text='Browse',
                                                   command=self.browse_input_iso)
        input_iso_button.grid(row=0, column=2, padx=(spacing, 0), pady=(0, spacing), sticky='ns')
        output_iso_button = customtkinter.CTkButton(master=main_frame,
                                                    text='Browse',
                                                    command=self.browse_output_iso)
        output_iso_button.grid(row=1, column=2, padx=(spacing, 0), pady=(0, spacing), sticky='ns')
        custom_tracks_button = customtkinter.CTkButton(master=main_frame,
                                                       text='Browse',
                                                       command=self.browse_custom_tracks_mods)
        custom_tracks_button.grid(row=2, column=2, padx=(spacing, 0), pady=0, sticky='n')
        self.custom_tracks_button_tool_tip = CTkToolTip.CTkToolTip(custom_tracks_button, delay=0.5)

        self.folder_mode_checkbox = customtkinter.CTkCheckBox(master=self,
                                                              text='Folder Mode',
                                                              command=self._sync_form)
        self.folder_mode_checkbox.grid(row=1,
                                       column=0,
                                       padx=padding,
                                       pady=(padding, padding),
                                       sticky='ns')
        if 'options' in config and config['options'].getboolean('folder_mode'):
            self.folder_mode_checkbox.select()
        tool_tip = '\n'.join(
            textwrap.wrap(
                'In Folder Mode, users are able to select custom tracks / mods that aren\' '
                'compressed in a ZIP archive and just stored in a folder. This allows for more '
                'rapid mod development. When choosing files in the file browser, select the folder '
                'that contains the folders of patches. Make sure that there are no unwanted '
                'folders in the selected folder.'))
        CTkToolTip.CTkToolTip(self.folder_mode_checkbox,
                              delay=0.5,
                              message=tool_tip,
                              justify='left')

        self.patch_button = customtkinter.CTkButton(master=self, text='Patch', command=self.patch)
        self.patch_button.grid(row=1, column=1, padx=padding, pady=(padding, padding), sticky='ns')

        self.input_iso_entry.insert(0, self._last_input_iso)
        self.output_iso_entry.insert(0, self._last_output_iso)
        self.custom_tracks_box.insert('0.0', self._last_custom_tracks)

        self._sync_form()

        self.input_iso_entry.bind('<KeyRelease>', lambda _event: self._sync_form())
        self.output_iso_entry.bind('<KeyRelease>', lambda _event: self._sync_form())
        self.custom_tracks_box.bind('<KeyRelease>', lambda _event: self._sync_form())

        self.protocol('WM_DELETE_WINDOW', self.close)

    def close(self):
        self._save_config()
        self.destroy()

    def browse_input_iso(self):
        initialdir, initialfile = get_initial_dir_and_file(self._last_input_iso,
                                                           self._last_input_iso_picked)

        input_iso = customtkinter.filedialog.askopenfilename(
            parent=self,
            title='Select Input ISO',
            initialdir=initialdir,
            initialfile=initialfile,
            filetypes=(('GameCube Disc Image', '*.iso *.gcm'), ),
        )

        if not input_iso:
            return

        self._last_input_iso_picked = input_iso

        self.input_iso_entry.delete(0, customtkinter.END)
        self.input_iso_entry.insert(0, input_iso)

        if not self.output_iso_entry.get():
            stem, ext = os.path.splitext(input_iso)
            output_iso = f'{stem}_new{ext}'
            self._last_output_iso_picked = output_iso
            self.output_iso_entry.insert(0, output_iso)

        self._sync_form()

    def browse_output_iso(self):
        initialdir, initialfile = get_initial_dir_and_file(self._last_output_iso,
                                                           self._last_output_iso_picked)

        output_iso = customtkinter.filedialog.asksaveasfilename(
            parent=self,
            title='Select Output ISO',
            initialdir=initialdir,
            initialfile=initialfile,
            filetypes=(('GameCube Disc Image', '*.iso *.gcm'), ),
        )

        if not output_iso:
            return

        self._last_output_iso_picked = output_iso

        self.output_iso_entry.delete(0, customtkinter.END)
        self.output_iso_entry.insert(0, output_iso)

        self._sync_form()

    def browse_custom_tracks_mods(self):
        initialdir, _initialfile = get_initial_dir_and_file(self._last_custom_tracks,
                                                            self._last_custom_tracks_picked)

        if not self.folder_mode_checkbox.get():
            custom_tracks = customtkinter.filedialog.askopenfilenames(
                parent=self,
                title='Select Custom Tracks / Mods',
                initialdir=initialdir,
                filetypes=(('MKDD Custom Tracks / Mods', '*.zip'), ),
                multiple=True)
            if not custom_tracks:
                return
            custom_tracks = '\n'.join(custom_tracks)
        else:
            custom_tracks = customtkinter.filedialog.askdirectory(
                parent=self,
                title='Select Custom Tracks / Mods',
                initialdir=initialdir,
                mustexist=True)
            if not custom_tracks:
                return

        self._last_output_iso_picked = custom_tracks

        self.custom_tracks_box.delete('0.0', customtkinter.END)
        self.custom_tracks_box.insert('0.0', custom_tracks)

        self._sync_form()

    def patch(self):
        input_iso = self.input_iso_entry.get().strip()
        output_iso = self.output_iso_entry.get().strip()
        custom_tracks = self.custom_tracks_box.get('0.0', customtkinter.END).splitlines()
        custom_tracks = tuple(path.strip() for path in custom_tracks if path.strip())

        def message_callback(title: str, icon: str, text: str):
            MessageBox(self, title, icon, text, '', False, ('Close', )).wait_answer()

        def prompt_callback(title: str, icon: str, text: str, buttons_labels: 'tuple[str]') -> bool:
            return MessageBox(self, title, icon, text, '', True, buttons_labels).wait_answer()

        def error_callback(title: str, icon: str, text: str):
            MessageBox(self, title, icon, text, '', False, ('Close', )).wait_answer()

        try:
            patcher_gui.PatcherHelper.patch(input_iso, output_iso, custom_tracks, message_callback,
                                            prompt_callback, error_callback)
        except Exception as e:
            MessageBox(self, 'Exception', 'error', 'An exception occurred :', str(e), False,
                       ('Close', )).wait_answer()

    def _sync_form(self):
        self._last_input_iso = self.input_iso_entry.get()
        self._last_output_iso = self.output_iso_entry.get()
        self._last_custom_tracks = self.custom_tracks_box.get('0.0', customtkinter.END)

        input_iso = self._last_input_iso.strip()
        output_iso = self._last_output_iso.strip()
        custom_tracks = tuple(p.strip() for p in self._last_custom_tracks.splitlines() if p.strip())

        if input_iso and output_iso and custom_tracks:
            self.patch_button.configure(
                state='normal', fg_color=customtkinter.ThemeManager.theme['CTkButton']['fg_color'])
        else:
            self.patch_button.configure(state='disabled', fg_color='#444')

        if self.folder_mode_checkbox.get():
            tool_tip = 'Select the directory that contains the custom track or mod.'
        else:
            tool_tip = 'Use the Ctrl and Shift keyboard modifiers to select multiple ZIP archives.'
        self.custom_tracks_button_tool_tip.configure(message=tool_tip)

        self._save_config()

    def _get_config(self):
        config = configparser.ConfigParser()

        try:
            with open(get_config_path(), 'r', encoding='utf-8') as f:
                config.read_file(f)
        except Exception:
            pass

        return config

    def _save_config(self):
        config = self._get_config()

        config['paths'] = {
            'input_iso': self._last_input_iso,
            'input_iso_picked': self._last_input_iso_picked,
            'output_iso': self._last_output_iso,
            'output_iso_picked': self._last_output_iso_picked,
            'custom_tracks': self._last_custom_tracks,
            'custom_tracks_picked': self._last_custom_tracks_picked,
        }

        config['geometry'] = {
            'window': str(self.geometry()).replace('+0+0', ''),
        }

        if 'options' not in config:
            config['options'] = {}

        config['options']['folder_mode'] = str(bool(self.folder_mode_checkbox.get())).lower()

        with open(get_config_path(), 'w', encoding='utf-8') as f:
            config.write(f)


class MessageBox(customtkinter.CTkToplevel):

    def __init__(self, master, title: str, icon: str, text: str, fixed_width_text: str,
                 prompter: bool, buttons_labels: 'tuple[str]'):
        super().__init__(master=master)

        self._accepted = False

        font_width, font_height = get_font_metrics()
        padding = int(font_width * 1.75)
        spacing = int(font_width * 0.75)

        dialog_width = font_width * 60
        dialog_height = font_height * 13

        if master is None:
            x = int((self.winfo_screenwidth() - dialog_width) / 2)
            y = int((self.winfo_screenheight() - dialog_height) / 2)
        else:
            x = int((master.winfo_width() - dialog_width) / 2 + master.winfo_x())
            y = int((master.winfo_height() - dialog_height) / 2 + master.winfo_y())

        self.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')
        self.minsize(font_width * 50, font_height * 12)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        icon_resolution = get_next_icon_resolution(font_width * 7)
        icon_path = get_icon_path(icon, icon_resolution)
        icon_image = Image.open(icon_path)
        image_label = customtkinter.CTkLabel(master=self,
                                             image=customtkinter.CTkImage(light_image=icon_image,
                                                                          dark_image=icon_image,
                                                                          size=(icon_resolution,
                                                                                icon_resolution)),
                                             text='')
        image_label.grid(row=0, column=0, padx=padding, pady=padding, sticky='nwe')

        main_frame = customtkinter.CTkFrame(master=self, fg_color='transparent')
        main_frame.grid(row=0, column=1, padx=(0, padding), pady=(padding, 0), sticky='nswe')
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        label = customtkinter.CTkLabel(master=main_frame, text=text, justify='left', anchor='nw')
        label.grid(row=0, column=0, padx=0, pady=0, sticky='nwe')

        if fixed_width_text:
            fixed_width_box = customtkinter.CTkTextbox(master=main_frame, wrap='none')
            fixed_width_box.grid(row=1, column=0, padx=0, pady=(spacing, 0), sticky='nswe')
            fixed_width_box.insert('0.0', fixed_width_text)
            fixed_width_box.configure(state='disabled')

        buttons_frame = customtkinter.CTkFrame(master=self, fg_color='transparent')
        buttons_frame.grid(row=1,
                           column=0,
                           columnspan=2,
                           padx=padding,
                           pady=(padding, padding),
                           sticky='nse')

        if prompter:
            buttons_labels = buttons_labels or ('No', 'Yes')
            no_button = customtkinter.CTkButton(master=buttons_frame,
                                                text=buttons_labels[0],
                                                command=self.close)
            no_button.grid(row=0, column=0, padx=(0, spacing), pady=0, sticky='nse')
            yes_button = customtkinter.CTkButton(master=buttons_frame,
                                                 text=buttons_labels[1],
                                                 command=self.accept)
            yes_button.grid(row=0, column=1, padx=0, pady=0, sticky='nse')
        else:
            buttons_labels = buttons_labels or ('Close', )
            close_button = customtkinter.CTkButton(master=buttons_frame,
                                                   text=buttons_labels[0],
                                                   command=self.close)
            close_button.grid(row=0, column=3, padx=0, pady=0, sticky='nse')

        self.title(title)
        if platform.system() == 'Windows':
            self.iconbitmap(get_ico_path(icon))
            # For some reason, on Windows only, customtkinter.CTkToplevel.__init__() sets an icon
            # change with a 200ms delay, which overrides our icon. To circumvent it, the method will
            # be monkey-patched so that it has no effect in future calls.
            self.iconbitmap = lambda _path: None
        else:
            logo = ImageTk.PhotoImage(file=get_icon_path(icon, ICON_RESOLUTIONS[-1]))
            self.iconphoto(False, logo)
        self.lift()
        self.attributes('-topmost', True)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Escape>', lambda _event: self.close())
        self.grab_set()

    def wait_answer(self) -> bool:
        self.master.wait_window(self)
        return self._accepted

    def close(self):
        self.grab_release()
        self.destroy()

    def accept(self):
        self._accepted = True
        self.grab_release()
        self.destroy()


def get_next_icon_resolution(resolution: int) -> int:
    for res in ICON_RESOLUTIONS:
        if res >= resolution:
            return res
    return ICON_RESOLUTIONS[-1]


def get_script_dir() -> str:
    return os.path.dirname(os.path.realpath(__file__))


def get_config_path() -> str:
    return os.path.join(get_script_dir(), 'config.ini')


def get_icon_path(name: str, resolution: int) -> str:
    return os.path.join(get_script_dir(), 'src', 'resources', f'{name}{resolution}.png')


def get_ico_path(name: str) -> str:
    return os.path.join(get_script_dir(), 'src', 'resources', f'{name}.ico')


def get_font_metrics() -> 'tuple[int, int]':
    font = customtkinter.CTkFont()
    font_width = font.measure('A')
    font_height = font.metrics('ascent') + font.metrics('descent')
    return font_width, font_height


def get_initial_dir_and_file(main_paths: str, fallback_paths: str) -> 'tuple[str, str]':
    for paths in (main_paths, fallback_paths):
        paths = paths.strip().splitlines()
        paths = tuple(p.strip() for p in paths if p.strip())
        if paths:
            path = paths[0]
            return os.path.dirname(path), os.path.basename(path)
    return '', ''


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    customtkinter.set_appearance_mode('dark')
    customtkinter.set_default_color_theme('dark-blue')

    # Match the style for the text-like widget types. Built-in themes seem to provide slightly
    # diffferent styles for each type (intentional, or oversight?).
    for widget_type in ('CTkEntry', 'CTkTextbox'):
        for field, value in (('border_width', 0), ('fg_color', ('#FCFCFC', '#303030'))):
            customtkinter.ThemeManager.theme[widget_type][field] = value

    app = MKDDPatcherApp()
    app.mainloop()
