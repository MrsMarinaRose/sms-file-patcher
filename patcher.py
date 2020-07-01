import tkinter as tk
import zipfile
import json 
import configparser
from io import BytesIO
from tkinter import filedialog
from tkinter import messagebox

from gcm import GCM
from track_mapping import arc_mapping, file_mapping, bsft
from dolreader import *
from rarc import Archive, write_pad32, write_uint32
from readbsft import BSFT
from zip_helper import ZipToIsoPatcher

GAMEID_TO_REGION = {
    b"GM4E": "US",
    b"GM4P": "PAL",
    b"GM4J": "JP"
}

LANGUAGES = ["English", "Japanese", "German", "Italian", "French", "Spanish"]


def copy_if_not_exist(iso, newfile, oldfile):
    if not iso.file_exists("files/"+newfile):
        iso.add_new_file("files/"+newfile, iso.read_file_data("files/"+oldfile))


def patch_baa(iso):
    baa = iso.read_file_data("files/AudioRes/GCKart.baa")
    baadata = baa.read()
    
    if b"COURSE_YCIRCUIT_0" in baadata:
        return # Baa is already patched, nothing to do
    
    bsftoffset = baadata.find(b"bsft")
    assert bsftoffset < 0x100
    
    baa.seek(len(baadata))
    new_bsft = BSFT()
    new_bsft.tracks = bsft
    write_pad32(baa)
    bsft_offset = baa.tell()
    new_bsft.write_to_file(baa)
    write_pad32(baa)
    baa.seek(bsftoffset)
    magic = baa.read(4)
    assert magic == b"bsft"
    write_uint32(baa, bsft_offset)
    iso.changed_files["files/AudioRes/GCKart.baa"] = baa
    print("patched baa")
    
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_YCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/COURSE_CIRCUIT_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_MCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/COURSE_CIRCUIT_0.x.32.c4.ast")
    

    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_CITY_0.x.32.c4.ast", "AudioRes/Stream/COURSE_HIWAY_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_COLOSSEUM_0.x.32.c4.ast", "AudioRes/Stream/COURSE_STADIUM_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_MOUNTAIN_0.x.32.c4.ast", "AudioRes/Stream/COURSE_JUNGLE_0.x.32.c4.ast")
    
    
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_YCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_CIRCUIT_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_MCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_CIRCUIT_0.x.32.c4.ast")
    

    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_CITY_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_HIWAY_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_COLOSSEUM_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_STADIUM_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_MOUNTAIN_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_JUNGLE_0.x.32.c4.ast")
    
    print("Copied ast files")
    
def patch_minimap_dol(dol, track, region, minimap_setting):
    with open("minimap_locations.json", "r") as f:
        addresses_json = json.load(f)
        addresses = addresses_json[region]
        corner1x, corner1z, corner2x, corner2z, orientation = addresses[track]

    orientation_val = minimap_setting["Orientation"]
    if orientation_val not in (0, 1, 2, 3):
        raise RuntimeError(
            "Invalid Orientation value: Must be in the range 0-3 but is {0}".format(orientation_val))

    dol.seek(int(orientation, 16))
    orientation_val = read_load_immediate_r0(dol)
    if orientation_val not in (0, 1, 2, 3):
        raise RuntimeError(
            "Wrong Address, orientation value in DOL isn't in 0-3 range: {0}. Maybe you are using"
            " a dol from a different game version?".format(orientation_val))

    dol.seek(int(orientation, 16))
    write_load_immediate_r0(dol, minimap_setting["Orientation"])
    dol.seek(int(corner1x, 16))
    write_float(dol, minimap_setting["Top Left Corner X"])
    dol.seek(int(corner1z, 16))
    write_float(dol, minimap_setting["Top Left Corner Z"])
    dol.seek(int(corner2x, 16))
    write_float(dol, minimap_setting["Bottom Right Corner X"])
    dol.seek(int(corner2z, 16))
    write_float(dol, minimap_setting["Bottom Right Corner Z"])


def rename_archive(arc, newname, mp):
    if mp:
        arc.root.name = newname+"l"
    else:
        arc.root.name = newname 
    
    rename = []
    
    for filename, file in arc.root.files.items():
        if "_" in filename:
            rename.append((filename, file))
    
    for filename, file in rename:
        del arc.root.files[filename]
        name, rest = filename.split("_", 1)
        
        if newname == "luigi2":
            newfilename = "luigi_"+rest 
        else:
            newfilename = newname + "_" + rest 
            
        file.name = newfilename
        arc.root.files[newfilename] = file 
        
        

class ChooseFilePath(tk.Frame):
    def __init__(self, master=None, description=None, file_chosen_callback=None, save=False):
        super().__init__(master)
        self.master = master
        self.pack(anchor="w") 
        
        self.label = tk.Label(self, text=description, width=20, anchor="w")
        self.label.pack(side="left")
        self.path = tk.Entry(self)
        self.path.pack(side="left")
        self.button = tk.Button(self, text="Open", command=self.open_file)
        
        if save:
            self.button["text"] = "Save"
            
        self.button.pack(side="left")
        self.save = save 
        self.callback = file_chosen_callback
        
    def open_file(self):
        if self.save:
            path = filedialog.asksaveasfilename()
        else:
            path = filedialog.askopenfilename()
        
        #print("path:" ,path)
        self.path.delete(0, tk.END)
        self.path.insert(0, path)
        
        if self.callback != None:
            self.callback(self)

class ChooseFilePathMultiple(tk.Frame):
    def __init__(self, master=None, description=None, save=False):
        super().__init__(master)
        self.master = master
        self.pack(anchor="w") 
        
        self.label = tk.Label(self, text=description, width=20, anchor="w")
        self.label.pack(side="left")
        self.path = tk.Entry(self)
        self.path.pack(side="left")
        self.button = tk.Button(self, text="Open", command=self.open_file)
        
        if save:
            self.button["text"] = "Save"
            
        self.button.pack(side="left")
        self.save = save 
        
        self.paths = []
        
        
    def open_file(self):
        paths = filedialog.askopenfilenames(title="Choose Race Track zip file(s)", 
        filetypes=(("MKDD Track Zip", "*.zip"), ))
        
        #print("path:" ,path)
        self.path.delete(0, tk.END)
        self.path.insert(0, paths[0])
        self.paths = paths 
        
        
    def get_paths(self):
        if not self.path.get():
            return []
        elif self.path.get() not in self.paths:
            return [self.path.get()]
        else:
            return self.paths
        

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()
    
    def make_open_button(self, master):
        button = tk.Button(master)
        button["text"] = "Open"
        return button 
    
    def update_path(self, widget):
        if widget.path.get() and not self.output_iso_path.path.get():
            self.output_iso_path.path.delete(0, tk.END)
            self.output_iso_path.path.insert(0, widget.path.get())
    
    def create_widgets(self):
        self.input_iso_path = ChooseFilePath(self, description="MKDD ISO", file_chosen_callback=self.update_path)
        
        self.input_track_path = ChooseFilePathMultiple(self, description="Race track zip")
        
        self.output_iso_path = ChooseFilePath(self, description="New ISO", save=True)
        
        self.frame = tk.Frame(self)
        self.frame.pack()
        self.patch_button = tk.Button(self.frame, text="Patch", command=self.patch)
        self.patch_button.pack()
        """self.hi_there = tk.Button(self)
        self.hi_there["text"] = "Hello World\n(click me)"
        self.hi_there["command"] = self.say_hi
        self.hi_there.pack(side="top")

        self.quit = tk.Button(self, text="QUIT", fg="red",
                              command=self.master.destroy)
        self.quit.pack(side="left")"""
    
    def patch(self):
        print("Input iso:", self.input_iso_path.path.get())
        print("Input track:", self.input_track_path.path.get())
        print("Output iso:", self.output_iso_path.path.get())
        
        if not self.input_iso_path.path.get():
            messagebox.showerror("Error", "You need to choose a MKDD ISO or GCM.")
            return 
        if not self.input_track_path.get_paths():
            messagebox.showerror("Error", "You need to choose a MKDD Race Track zip file.")
            return 
        
        with open(self.input_iso_path.path.get(), "rb") as f:
            gameid = f.read(4)
        
        if gameid not in GAMEID_TO_REGION:
            messagebox.showerror("Error", "Unknown Game ID: {}. Probably not a MKDD ISO.".format(gameid))
            return 
            
        region = GAMEID_TO_REGION[gameid]
        print("Patching now")
        isopath = self.input_iso_path.path.get()
        iso = GCM(isopath)
        iso.read_entire_disc()
        
        patcher = ZipToIsoPatcher(None, iso)
        
        
        for track in self.input_track_path.get_paths():
            print(track)
            trackzip = zipfile.ZipFile(track)
            patcher.zip = trackzip 
            
            
            config = configparser.ConfigParser()
            trackinfo = trackzip.open("trackinfo.ini")
            config.read_string(str(trackinfo.read(), encoding="utf-8"))
            
            #use_extended_music = config.getboolean("Config", "extended_music_slots")
            replace = config["Config"]["replaces"].strip()
            replace_music = config["Config"]["replaces_music"].strip()
            
            print("Imported Track Info:")
            print("Track '{0}' created by {1} replaces {2}".format(
                config["Config"]["trackname"], config["Config"]["author"], config["Config"]["replaces"])
                )
            
            minimap_settings = json.load(trackzip.open("minimap.json"))
            
            
            
            
            
            # Patch minimap settings in dol 
            dol = DolFile(patcher.get_iso_file("sys/main.dol"))
            patch_minimap_dol(dol, replace, region, minimap_settings)
            dol._rawdata.seek(0)
            patcher.change_file("sys/main.dol", dol._rawdata)
            
            bigname, smallname = arc_mapping[replace]
            _, _, bigbanner, smallbanner, trackname, trackimage = file_mapping[replace]
            normal_music, fast_music = file_mapping[replace_music][0:2]
            # Copy staff ghost 
            patcher.copy_file("staffghost.ght", "files/StaffGhosts/{}.ght".format(bigname))
            
            # Copy track arc 
            track_arc = Archive.from_file(trackzip.open("track.arc"))
            track_mp_arc = Archive.from_file(trackzip.open("track_mp.arc"))
            rename_archive(track_arc, smallname, False)
            rename_archive(track_mp_arc, smallname, True)
            
            newarc = BytesIO()
            track_arc.write_arc_uncompressed(newarc)
            
            newarc_mp = BytesIO()
            track_mp_arc.write_arc_uncompressed(newarc_mp)
            
            patcher.change_file("files/Course/{}.arc".format(bigname), newarc)
            patcher.change_file("files/Course/{}L.arc".format(bigname), newarc_mp)
             
            print("replacing", "files/Course/{}.arc".format(bigname))
            if bigname == "Luigi2":
                bigname = "Luigi"
            if smallname == "luigi2":
                smallname = "luigi"
            # Copy language images 
            missing_languages = []
            main_language = config["Config"]["main_language"]
            
            for srclanguage in LANGUAGES:
                dstlanguage = srclanguage
                if not patcher.src_file_exists("course_images/{}/".format(srclanguage)):
                    #missing_languages.append(srclanguage)
                    #continue
                    srclanguage = main_language
                
                
                coursename_arc_path = "files/SceneData/{}/coursename.arc".format(dstlanguage)
                courseselect_arc_path = "files/SceneData/{}/courseselect.arc".format(dstlanguage)
                if not iso.file_exists(coursename_arc_path):
                    continue 
                
                #print("Found language", language)
                
                
                coursename_arc = Archive.from_file(patcher.get_iso_file(coursename_arc_path))
                courseselect_arc = Archive.from_file(patcher.get_iso_file(courseselect_arc_path))

                patcher.copy_file("course_images/{}/track_big_logo.bti".format(srclanguage),
                                "files/CourseName/{}/{}_name.bti".format(dstlanguage, bigname))

                patcher.copy_file_into_arc("course_images/{}/track_small_logo.bti".format(srclanguage),
                            coursename_arc, "coursename/timg/{}_names.bti".format(smallname))
                patcher.copy_file_into_arc("course_images/{}/track_name.bti".format(srclanguage),
                            courseselect_arc, "courseselect/timg/{}".format(trackname))
                patcher.copy_file_into_arc("course_images/{}/track_image.bti".format(srclanguage),
                            courseselect_arc, "courseselect/timg/{}".format(trackimage))


                newarc = BytesIO()
                coursename_arc.write_arc_uncompressed(newarc)
                newarc.seek(0)
                
                newarc_mp = BytesIO()
                courseselect_arc.write_arc_uncompressed(newarc_mp)
                newarc_mp.seek(0)
                patcher.change_file("files/SceneData/{}/coursename.arc".format(dstlanguage), newarc)
                patcher.change_file("files/SceneData/{}/courseselect.arc".format(dstlanguage), newarc_mp) 
            
            
            # Copy over the normal and fast music
            # Note: if the fast music is missing, the normal music is used as fast music 
            # and vice versa. If both are missing, no copying is happening due to behaviour of
            # copy_or_add_file function
            patcher.copy_or_add_file("lap_music_normal.ast", "files/AudioRes/Stream/{}".format(normal_music))
            patcher.copy_or_add_file("lap_music_fast.ast", "files/AudioRes/Stream/{}".format(fast_music))
            if not patcher.src_file_exists("lap_music_normal.ast"):
                patcher.copy_or_add_file("lap_music_fast.ast", "files/AudioRes/Stream/{}".format(normal_music))
            if not patcher.src_file_exists("lap_music_fast.ast"):
                patcher.copy_or_add_file("lap_music_normal.ast", "files/AudioRes/Stream/{}".format(fast_music))

        patch_baa(iso)
        print("loaded")
        print("writing iso")
        print("all changed files:", iso.changed_files.keys())
        iso.export_disc_to_iso_with_changed_files(self.input_iso_path.path.get()+"new.iso")
        print("written") 
        
    def say_hi(self):
        print("hi there, everyone!")
        
if __name__ == "__main__":
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()