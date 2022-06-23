import cv2
import time
import keyboard
from automap_finder import toggle_automap
from char.i_char import IChar
from config import Config
from logger import Logger
from pather import Location, Pather
from item.pickit import PickIt
import template_finder
from town.town_manager import TownManager, A4
from utils.misc import cut_roi, wait
from utils.custom_mouse import mouse
from screen import convert_abs_to_monitor, convert_abs_to_screen, convert_monitor_to_screen, grab
from ui_manager import detect_screen_object, ScreenObjects
from ui import skills, loading, waypoint
from inventory import belt, personal

class Diablo:

    name = "run_diablo"

    def __init__(
        self,
        pather: Pather,
        town_manager: TownManager,
        char: IChar,
        pickit: PickIt,
        runs: list[str]
    ):
        self._pather = pather
        self._town_manager = town_manager
        self._char = char
        self._pickit = pickit
        self._picked_up_items = False
        self.used_tps = 0
        self._curr_loc: bool | Location = Location.A4_TOWN_START
        self._runs = runs

        
    def _sealdance(self, seal_opentemplates: list[str], seal_closedtemplates: list[str], seal_layout: str, seal_node: str) -> bool:
        i = 0
        while i < 4:
            if Config().general["use_automap_navigation"] == 1 : toggle_automap(False) # just to ensure we switch off Automap, so it does not interfere with sealcheck
            Logger.debug(seal_layout + ": trying to open (try #" + str(i+1)+")")
            self._char.select_by_template(seal_closedtemplates, threshold=0.5, timeout=0.1, telekinesis=True)
            wait(i*1)
            found = template_finder.search_and_wait(seal_opentemplates, threshold=0.75, timeout=0.1).valid
            if found:
                Logger.info(seal_layout +": is open - "+'\033[92m'+" open"+'\033[0m')
                break
            else:
                Logger.debug(seal_layout +": is closed - "+'\033[91m'+" closed"+'\033[0m')
                pos_m = convert_abs_to_monitor((0, 0))
                mouse.move(*pos_m, randomize=[90, 160])
                wait(0.3)
                if i >= 1:
                    Logger.debug(seal_layout + ": failed " + str(i+2) + " times, trying to kill trash now")
                    Logger.debug("Sealdance: Kill trash at location: sealdance")
                    self._char.dia_kill_trash("sealdance")
                    wait(i*0.5)
                    Logger.debug("Sealdance: Recalibrating at seal_node")
                    if not self._pather.traverse_nodes_automap(seal_node, self._char): return False
                else:
                    direction = 1 if i % 2 == 0 else -1
                    x_m, y_m = convert_abs_to_monitor([50 * direction, direction])
                    self._char.move((x_m, y_m), force_move=True)
                i += 1
        if Config().general["info_screenshots"] and not found: cv2.imwrite(f"./log/screenshots/info/info_failed_seal_" + seal_layout + "_" + time.strftime("%Y%m%d_%H%M%S") + ".png", grab())
        return found


# BUY POTS & STASH WHEN AT PENTAGRAM
    def _cs_town_visit(self, location:str) -> bool:
        Logger.debug("CS Town_visits is currently not implemented")
        return True

    def approach(self, start_loc: Location) -> bool | Location:
        Logger.info("Run Diablo")
        if not (self._char.capabilities.can_teleport_natively or self._char.capabilities.can_teleport_with_charges):
            raise ValueError("Diablo requires teleport")
        if not self._town_manager.open_wp(start_loc):
            return False
        wait(0.4)
        waypoint.use_wp("River of Flame")
        return Location.A4_DIABLO_WP


    def battle(self, do_pre_buff: bool) -> bool | tuple[Location, bool]:
        self._picked_up_items = False
        self.used_tps = 0
        if do_pre_buff: self._char.pre_buff()

        ##############
        # WP to PENT #
        ##############
        
        #Teleport directly
        if self._char.capabilities.can_teleport_natively:
            self._pather.traverse_nodes_fixed("dia_wp_cs-e", self._char) #Traverse River of Flame (no chance to traverse w/o fixed, there is no reference point between WP & CS Entrance) - minimum 3 teleports are needed, if we only cross the gaps (maybe loop template matching the gap, otherwise walking), otherwise its 9

        #Traverse ROF with minimal teleport charges
        elif not self._char.run_to_cs() and self._char.capabilities.can_teleport_with_charges:
            Logger.debug("ROF: Let's run to the ROF diving board!")

            pos_m = convert_abs_to_monitor((620, -350))
            self._char.walk(pos_m, force_move=True) # walk away from wp
            # go to the first jumping spot at ROF
            if not self._pather.traverse_nodes_automap([1601, 1602], self._char, timeout=2, force_move=True): return False
            path_to_cs_entrance = [convert_abs_to_screen((620, -350))] * 7
            self._pather.traverse_nodes_fixed(path_to_cs_entrance, self._char)

            """
            # Minimal Teleport Charge Version, too hacky.

            Logger.debug("ROF: Teleporting across GAP1")
            mouse.move(*pos_m, randomize=0, delay_factor=[0.5, 0.7])
            skills.select_tp(Config().char["teleport"])
            mouse.click(button="right")
            wait(0.3,0.4)

            roi = Config().ui_roi["dia_am_rof"]
            while not template_finder.search_and_wait(["DIA_AM_ROF_GAP"], threshold=0.8, timeout=0.2, roi=roi).valid: # check1 using primary templates
                Logger.debug("ROF: Teleporting the rest towards CS Entrance")
                pos_m = convert_abs_to_monitor((620, -350))
                mouse.move(*pos_m, randomize=0, delay_factor=[0.5, 0.7])
                #keyboard.send(Config().char["force_move"])
                keyboard.send("e")
                self._char.move(pos_m, force_move=True, force_tp=False)
                #count =+ 1

            Logger.debug("ROF: GAP found, teleporting across GAP2")
            pos_m = convert_abs_to_monitor((620, -350))
            mouse.move(*pos_m, randomize=0, delay_factor=[0.5, 0.7])
            skills.select_tp(Config().char["teleport"])
            mouse.click(button="right")
            wait(0.3,0.4)

            roi = Config().ui_roi["dia_am_rof"]
            while not template_finder.search_and_wait(["DIA_AM_ROF_GAP"], threshold=0.8, timeout=0.2, roi=roi).valid: # check1 using primary templates
                Logger.debug("ROF: Walking towards CS Entrance, searching for next GAP")
                pos_m = convert_abs_to_monitor((620, -350))
                mouse.move(*pos_m, randomize=0, delay_factor=[0.5, 0.7])
                #keyboard.send(Config().char["force_move"])
                keyboard.send("e")
                self._char.move(pos_m, force_move=True, force_tp=False)
                #count =+ 1
                img = grab()
                roi = Config().ui_roi["dia_am_rof"]
                pic = cut_roi(img, roi)
                cv2.imwrite("./log/cutroi.png", pic)

            Logger.debug("ROF: GAP found, teleporting across GAP3")
            pos_m = convert_abs_to_monitor((620, -350))
            mouse.move(*pos_m, randomize=0, delay_factor=[0.5, 0.7])
            skills.select_tp(Config().char["teleport"])
            mouse.click(button="right")
            wait(0.3,0.4)

            while not template_finder.search_and_wait(["DIA_AM_CS"], threshold=0.8, timeout=0.2).valid: # check1 using primary templates
                Logger.debug("ROF: Walking towards CS Entrance, searching for CS Entrance")
                pos_m = convert_abs_to_monitor((620, -350))
                mouse.move(*pos_m, randomize=0, delay_factor=[0.5, 0.7])
                #keyboard.send(Config().char["force_move"])
                keyboard.send("e")
                #keyboard.send(self._skill_hotkeys["vigor"])
                self._char.move(pos_m, force_move=True, force_tp=False)
                #count =+ 1
            """
            Logger.debug("ROF: found CS Entrance!")
            #self._pather.traverse_nodes_fixed("dia_tyrael_cs-e", self._char) #never teleports, always walks...

        else: 
            raise ValueError("Diablo requires teleport")

        #So we finally arrived at CS Entrance
        if not self._pather.traverse_nodes_automap([1605], self._char): return False # Calibrate at CS Entrance
        Logger.debug("ROF: Calibrated at CS ENTRANCE")
        
        #make leecher TP
        if Config().char["dia_leecher_tp_cs"]:
            Logger.debug("CS: OPEN LEECHER TP AT ENTRANCE")
            self._char.dia_kill_trash("aisle_2") #clear the area aound TP #DIA_CLEAR_TRASH=1 , DIA_CS_LEECHER_TP=1
            if not skills.has_tps(): Logger.warning("CS: failed to open TP, you should buy new TPs!")
            mouse.click(button="right")
                
        #############################
        # KILL TRASH IN CS ENTRANCE #
        #############################

        if Config().char["dia_kill_trash"]:
            #Logger.debug("Kill Trash CS -> Pent not implemented yet")

            if not self._pather.traverse_nodes_automap([1500], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: outside_cs")
            self._char.dia_kill_trash("outside_cs")

            if not self._pather.traverse_nodes_automap([1501], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: outside_cs_stairs")
            self._char.dia_kill_trash("outside_cs_stairs")

            if not self._pather.traverse_nodes_automap([1502], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: aisle_1")
            self._char.dia_kill_trash("aisle_1")

            if not self._pather.traverse_nodes_automap([1503], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: aisle_2")
            self._char.dia_kill_trash("aisle_2")

            if not self._pather.traverse_nodes_automap([1504], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: aisle_3")
            self._char.dia_kill_trash("aisle_3")

            if not self._pather.traverse_nodes_automap([1505], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: aisle_4")
            self._char.dia_kill_trash("aisle_4")

            if not self._pather.traverse_nodes_automap([1506], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall1_1")
            self._char.dia_kill_trash("hall1_1")

            if not self._pather.traverse_nodes_automap([1507], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall1_2")
            self._char.dia_kill_trash("hall1_2")

            if not self._pather.traverse_nodes_automap([1508], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall1_3")
            self._char.dia_kill_trash("hall1_3")

            if not self._pather.traverse_nodes_automap([1509], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall1_4")
            self._char.dia_kill_trash("hall1_4")

            if not self._pather.traverse_nodes_automap([1510], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: to_hall2_1")
            self._char.dia_kill_trash("to_hall2_1")

            if not self._pather.traverse_nodes_automap([1511], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: to_hall2_2")
            self._char.dia_kill_trash("to_hall2_2")

            if not self._pather.traverse_nodes_automap([1512], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: to_hall2_3")
            self._char.dia_kill_trash("to_hall2_3")

            if not self._pather.traverse_nodes_automap([1513], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: to_hall2_4")
            self._char.dia_kill_trash("to_hall2_4")

            if not self._pather.traverse_nodes_automap([1514], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall2_1")
            self._char.dia_kill_trash("hall2_1")

            if not self._pather.traverse_nodes_automap([1515], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall2_2")
            self._char.dia_kill_trash("hall2_2")

            if not self._pather.traverse_nodes_automap([1516], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall2_3")
            self._char.dia_kill_trash("hall2_3")

            if not self._pather.traverse_nodes_automap([1517], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall2_4")
            self._char.dia_kill_trash("hall2_4")

            if not self._pather.traverse_nodes_automap([1516,1514,1518], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: to_hall3_1")
            self._char.dia_kill_trash("to_hall3_1")

            if not self._pather.traverse_nodes_automap([1519], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: to_hall3_2")
            self._char.dia_kill_trash("to_hall3_2")

            if not self._pather.traverse_nodes_automap([1520], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: to_hall3_3")
            self._char.dia_kill_trash("to_hall3_3")

            #if not self._pather.traverse_nodes_automap([1521], self._char): return False #weak node, gets stuck often as walker, because the CS template is covered by the UI
            #Logger.debug("CS TRASH: Killing Trash at: hall3_1")
            #self._char.dia_kill_trash("hall3_1")

            if not self._pather.traverse_nodes_automap([1522], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall3_2")
            self._char.dia_kill_trash("hall3_2")

            if not self._pather.traverse_nodes_automap([1523], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall3_3")
            self._char.dia_kill_trash("hall3_3")

            if not self._pather.traverse_nodes_automap([1524], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall3_4")
            self._char.dia_kill_trash("hall3_4")

            if not self._pather.traverse_nodes_automap([1525], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall3_5")
            self._char.dia_kill_trash("hall3_5")

            #Trash to Pent Walking = [1500, 1501, 1502, 1503, 1504, 1505, 1506, 1507, 1508, 1509, 1510, 1511, 1512, 1513, 1514, 1515, 1516, 1517, 1516, 1514, 1518, 1519, 1520, 1521, 1522, 1523, 1524, 1610]
                    
        else:
            #we kill no trash
            Logger.debug("ROF: Teleporting directly to PENTAGRAM")
            self._pather.traverse_nodes_fixed("dia_cs-e_pent", self._char) #Skip killing CS Trash & directly go to PENT, thereby revelaing key templates
        
        if not self._pather.traverse_nodes_automap([1610], self._char): return False # calibrate at Pentagram
        Logger.info("CS: Calibrated at PENTAGRAM")

        #make leecher TP
        if Config().char["dia_leecher_tp_pent"]:
            Logger.debug("CS: OPEN LEECHER TP AT ENTRANCE")
            self._char.dia_kill_trash("pent_before_a")
            if not skills.has_tps(): Logger.warning("CS: failed to open TP, you should buy new TPs!")
            mouse.click(button="right")

        ##########
        # Seal A #
        ##########

        # Settings
        static_layoutcheck = "dia_am_lc_a"
        sealname = "A"
        boss = "Vizier"
        seal_layout1= "A1-L"
        seal_layout2= "A2-Y"

        calibration_node = [1620]
        calibration_threshold = 0.8
        
        templates_primary= ["DIA_AM_A2Y"]
        threshold_primary= 0.8
                
        templates_confirmation= ["DIA_AM_A1L"]
        confirmation_node= None 
        confirmation_node2=None
        threshold_confirmation= 0.8
        threshold_confirmation2= 0.8
  
        ###############
        # PREPARATION #
        ###############
        
        #if Config().char["dia_town_visits"]: self._cs_town_visit("A")
        if do_pre_buff and Config().char["dia_kill_trash"]: self._char.pre_buff() #only for dia_kill_trash
        self._char.dia_kill_trash("pent_before_a") # Clear Pentagram

        #############################
        # KILL TRASH TOWARDS SEAL A #
        #############################

        if Config().char["dia_kill_trash"]:
            Logger.debug("CS TRASH: Kill Trash between Pentagram and Layoutcheck A")

            if not self._pather.traverse_nodes_automap([1525], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall3_5")
            self._char.dia_kill_trash("hall3_5")

            if not self._pather.traverse_nodes_automap([1526], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: trash_to_a1")
            self._char.dia_kill_trash("trash_to_a1")

            if not self._pather.traverse_nodes_automap([1527], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: trash_to_a2")
            self._char.dia_kill_trash("trash_to_a2")

            if not self._pather.traverse_nodes_automap([1528], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: trash_to_a3")
            self._char.dia_kill_trash("trash_to_a3")

            if not self._pather.traverse_nodes_automap([1529], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: trash_to_a4")
            self._char.dia_kill_trash("trash_to_a4")

            if not self._pather.traverse_nodes_automap([1627], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: a_boss")
            self._char.dia_kill_trash("a_boss")
       
        ###############
        # LAYOUTCHECK #
        ###############

        if not self._pather.traverse_nodes_automap(calibration_node, self._char, threshold=calibration_threshold, toggle_map=True): return False
        self._char.dia_kill_trash("layoutcheck_a") # Clear Trash & Loot at Layout Check
        Logger.debug("==============================")
        Logger.debug(f"{sealname}: Checking Layout for "f"{boss}")
        
        if not calibration_node == None:
            if not self._pather.traverse_nodes_automap(calibration_node, self._char, threshold=calibration_threshold,): return False
        
        toggle_automap(True)
        pos_m = convert_abs_to_monitor((640, 360)) # move mouse away during LC to not hover items obscuring the minimap
        mouse.move(*pos_m, delay_factor=[0.1, 0.2]) # move mouse away during LC to not hover items obscuring the minimap
        wait(0.25, 0.35)
        if not template_finder.search_and_wait(templates_primary, threshold =threshold_primary, timeout=0.2).valid: # check1 using primary templates
            toggle_automap(False)
            Logger.debug(f"{seal_layout1}: Layout_check step 1/2 - templates NOT found for "f"{seal_layout2}")
        
            if not confirmation_node == None: # cross-check for confirmation
                if not self._pather.traverse_nodes_automap(confirmation_node, self._char, threshold=calibration_threshold, toggle_map=True): return False
        
            toggle_automap(True)
            pos_m = convert_abs_to_monitor((640, 360)) # move mouse away during LC to not hover items obscuring the minimap
            mouse.move(*pos_m, delay_factor=[0.1, 0.2]) # move mouse away during LC to not hover items obscuring the minimap
            wait(0.25, 0.35)
            if not template_finder.search_and_wait(templates_confirmation, threshold=threshold_confirmation, timeout=0.2).valid:
                toggle_automap(False)
                Logger.warning(f"{seal_layout2}: Layout_check failure - could not determine the seal Layout at " f"{sealname} ("f"{boss}) - "+'\033[91m'+"aborting run"+'\033[0m')
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout1 + "_LC_fail" + time.strftime("%Y%m%d_%H%M%S") + ".png", grab())
                toggle_automap(True)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout1 + "_LC_fail" + time.strftime("%Y%m%d_%H%M%S") + "automap.png", grab())
                return False
        
            else:
                Logger.info(f"{seal_layout1}: Layout_check step 2/2 - templates found for "f"{seal_layout1} - "+'\033[93m'+"all fine, proceeding with "f"{seal_layout1}"+'\033[0m')
                
                ###################
                # Clear Seal A1-L #
                ###################
                
                #Settings
                seal_layout = seal_layout1
                node_seal1_automap=[1621] # Fake
                node_seal2_automap=[1622] # Boss
                seal1_opentemplates=["DIA_A1L2_14_OPEN"] # Fake
                seal1_closedtemplates=["DIA_A1L2_14_CLOSED", "DIA_A1L2_14_CLOSED_DARK", "DIA_A1L2_14_MOUSEOVER"] # Fake
                seal2_opentemplates=["DIA_A1L2_5_OPEN"] # Boss
                seal2_closedtemplates=["DIA_A1L2_5_CLOSED","DIA_A1L2_5_MOUSEOVER"] # Boss
                
                #CLEAR TRASH
                if Config().char["dia_kill_trash"]:
                    Logger.info(seal_layout +": Starting to clear seal")
                    Logger.debug("Kill Trash at SEAL A not implemented yet")
                    Logger.debug(seal_layout + "_01: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_01")
                    Logger.debug(seal_layout + "_02: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_02")
                    Logger.debug(seal_layout + "_03: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_03")
            
                #SEAL
                toggle_automap(False) # just to be safe
                Logger.info(seal_layout +": Starting to pop seals")
                if not self._pather.traverse_nodes_automap(node_seal1_automap, self._char): return False # Calibrate at Fake seal 
                if not self._sealdance(seal1_opentemplates, seal1_closedtemplates, seal_layout + ": Seal1", node_seal1_automap): return False # Open Fake seal
                if not self._pather.traverse_nodes_automap(node_seal2_automap, self._char): return False # Calibrate at Boss seal
                if not self._sealdance(seal2_opentemplates, seal2_closedtemplates, seal_layout + ": Seal2", node_seal2_automap): return False # Open Boss Seal
                Logger.debug(seal_layout + ": Kill Boss A (Vizier)") 
                self._char.kill_vizier_automap(seal_layout) # Kill Boss
                Logger.debug(seal_layout + ": Traversing back to Pentagram")
                if not self._pather.traverse_nodes_automap([1610], self._char): return False # go to Pentagram
                Logger.info(seal_layout + ": finished seal & calibrated at PENTAGRAM")
                
        
        else:
            Logger.debug(f"{seal_layout2}: Layout_check step 1/2 - templates found for {seal_layout1}")
        
            if not confirmation_node2 == None: # cross-check for confirmation
                if not self._pather.traverse_nodes_automap(confirmation_node2, self._char, threshold=calibration_threshold,): return False
            
            toggle_automap(True)
            pos_m = convert_abs_to_monitor((640, 360)) # move mouse away during LC to not hover items obscuring the minimap
            mouse.move(*pos_m, delay_factor=[0.1, 0.2]) # move mouse away during LC to not hover items obscuring the minimap
            wait(0.25, 0.35)
            if not template_finder.search_and_wait(templates_confirmation, threshold=threshold_confirmation2, timeout=0.2).valid:
                toggle_automap(False)
                Logger.info(f"{seal_layout2}: Layout_check step 2/2 - templates NOT found for "f"{seal_layout1} - "+'\033[96m'+"all fine, proceeding with "f"{seal_layout2}"+'\033[0m')
                
                ###################
                # Clear Seal A2-Y #
                ###################
                
                #Settings
                seal_layout = seal_layout2
                node_seal1_automap=[1620] # Fake
                node_seal2_automap=[1625] # Boss
                seal1_opentemplates=["DIA_A2Y4_29_OPEN"] # Fake
                seal1_closedtemplates=["DIA_A2Y4_29_CLOSED", "DIA_A2Y4_29_MOUSEOVER"] # Fake
                seal2_opentemplates=["DIA_A2Y4_36_OPEN"] # Boss
                seal2_closedtemplates=["DIA_A2Y4_36_CLOSED", "DIA_A2Y4_36_MOUSEOVER"] # Boss

                #CLEAR TRASH
                if Config().char["dia_kill_trash"]:
                    Logger.info(seal_layout +": Starting to clear seal")
                    Logger.debug("Kill Trash at SEAL A not implemented yet")
                    Logger.debug(seal_layout + "_01: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_01")
                    Logger.debug(seal_layout + "_02: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_02")
                    Logger.debug(seal_layout + "_03: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_03")

                #SEAL
                toggle_automap(False) # just to be safe
                Logger.info(seal_layout +": Starting to pop seals")
                if not self._pather.traverse_nodes_automap(node_seal1_automap, self._char): return False # Calibrate at Fake seal 
                if not self._sealdance(seal1_opentemplates, seal1_closedtemplates, seal_layout + ": Seal1", node_seal1_automap): return False # Open Fake seal
                if not self._pather.traverse_nodes_automap(node_seal2_automap, self._char): return False # Calibrate at Boss seal 
                if not self._sealdance(seal2_opentemplates, seal2_closedtemplates, seal_layout + ": Seal2", node_seal2_automap): return False # Open Boss seal
                Logger.debug(seal_layout + ": Kill Boss A (Vizier)")
                self._char.kill_vizier_automap(seal_layout)
                Logger.debug(seal_layout + ": Traversing back to Pentagram")
                if not self._pather.traverse_nodes_automap([1610], self._char): return False
                Logger.info(seal_layout + ": finished seal & calibrated at PENTAGRAM")
                

            else:
                Logger.warning(f"{seal_layout2}: Layout_check failure - could not determine the seal Layout at " f"{sealname} ("f"{boss}) - "+'\033[91m'+"aborting run"+'\033[0m')
                wait(5)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout2 + "_LC_fail_" + time.strftime("%Y%m%d_%H%M%S") + ".png", grab())
                toggle_automap(True)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout2 + "_LC_fail" + time.strftime("%Y%m%d_%H%M%S") + "automap.png", grab())
                return False
    
        
        ##########
        # Seal B #
        ##########

        # Settings
        static_layoutcheck = "dia_am_lc_b"
        sealname = "B"
        boss = "De Seis"
        seal_layout1= "B2-U"
        seal_layout2= "B1-S"

        calibration_node = [1630]
        calibration_threshold = 0.78
        
        templates_primary= ["DIA_AM_B1S", "DIA_AM_B1S_1", "DIA_AM_B1S_2"]
        threshold_primary= 0.72
                
        templates_confirmation= ["DIA_AM_B2U"]
        confirmation_node=[1630] 
        confirmation_node2=None
        threshold_confirmation= 0.75
        threshold_confirmation2= 0.75

        ###############
        # PREPARATION #
        ###############
        
        #if Config().char["dia_town_visits"]: self._cs_town_visit("B")
        
        if do_pre_buff and Config().char["dia_kill_trash"]: self._char.pre_buff() #only for dia_kill_trash
        self._char.dia_kill_trash("pent_before_b") # Clear Pentagram

        #############################
        # KILL TRASH TOWARDS SEAL B #
        #############################

        if Config().char["dia_kill_trash"]:
            Logger.debug("CS TRASH: Kill Trash between Pentagram and Layoutcheck B")

            if not self._pather.traverse_nodes_automap([1530], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: hall3_5")
            self._char.dia_kill_trash("hall3_5")

            if not self._pather.traverse_nodes_automap([1531], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: trash_to_b1")
            self._char.dia_kill_trash("trash_to_b1")

            if not self._pather.traverse_nodes_automap([1532], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: trash_to_b2")
            self._char.dia_kill_trash("trash_to_b2")

            if not self._pather.traverse_nodes_automap([1633], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: approach_b1s")
            self._char.dia_kill_trash("approach_b1s")

            if not self._pather.traverse_nodes_automap([1638], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: approach_b2u")
            self._char.dia_kill_trash("approach_b2u")

            if not self._pather.traverse_nodes_automap([1632], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: b_boss")
            self._char.dia_kill_trash("a_boss")

            if not self._pather.traverse_nodes_automap([1635], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: b_boss_seal")
            self._char.dia_kill_trash("b_boss_seal")
        
        ###############
        # LAYOUTCHECK #
        ###############

        if not self._pather.traverse_nodes_automap(calibration_node, self._char, threshold=calibration_threshold, toggle_map=True): return False
        self._char.dia_kill_trash("layoutcheck_b")
        Logger.debug("==============================")
        Logger.debug(f"{sealname}: Checking Layout for "f"{boss}")
        
        if not calibration_node == None:
            if not self._pather.traverse_nodes_automap(calibration_node, self._char, threshold=calibration_threshold, toggle_map=True): return False
        
        toggle_automap(True)
        pos_m = convert_abs_to_monitor((640, 360)) # move mouse away during LC to not hover items obscuring the minimap
        mouse.move(*pos_m, delay_factor=[0.1, 0.2]) # move mouse away during LC to not hover items obscuring the minimap
        wait(0.25, 0.35)
        if not template_finder.search_and_wait(templates_primary, threshold =threshold_primary, timeout=0.2).valid: #check1 using primary templates
            toggle_automap(False)
            Logger.debug(f"{seal_layout1}: Layout_check step 1/2 - templates NOT found for "f"{seal_layout2}")
            
            if not confirmation_node == None:#cross-check for confirmation
                if not self._pather.traverse_nodes_automap(confirmation_node, self._char, threshold=calibration_threshold, toggle_map=True): return False

            toggle_automap(True)
            pos_m = convert_abs_to_monitor((640, 360)) # move mouse away during LC to not hover items obscuring the minimap
            mouse.move(*pos_m, delay_factor=[0.1, 0.2]) # move mouse away during LC to not hover items obscuring the minimap
            wait(0.25, 0.35)
            if not template_finder.search_and_wait(templates_confirmation, threshold=threshold_confirmation, timeout=0.2).valid:
                toggle_automap(False)
                Logger.warning(f"{seal_layout2}: Layout_check failure - could not determine the seal Layout at " f"{sealname} ("f"{boss}) - "+'\033[91m'+"aborting run"+'\033[0m')
                wait(5)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout1 + "_LC_fail" + time.strftime("%Y%m%d_%H%M%S") + ".png", grab())
                toggle_automap(True)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout1 + "_LC_fail" + time.strftime("%Y%m%d_%H%M%S") + "automap.png", grab())
                return False
        
            else:
                Logger.info(f"{seal_layout1}: Layout_check step 2/2 - templates found for "f"{seal_layout1} - "+'\033[93m'+"all fine, proceeding with "f"{seal_layout1}"+'\033[0m')
                
                ###################
                # Clear Seal B2-U #
                ###################
                
                #Settings
                seal_layout = seal_layout1
                node_seal1_automap=None #Fake
                node_seal2_automap=[1635] #Boss
                seal1_opentemplates=None
                seal1_closedtemplates=None
                seal2_opentemplates=["DIA_B2U2_16_OPEN"]
                seal2_closedtemplates=["DIA_B2U2_16_CLOSED", "DIA_B2U2_16_MOUSEOVER"]

                #CLEAR TRASH
                if Config().char["dia_kill_trash"]:
                    Logger.info(seal_layout +": Starting to clear seal")
                    Logger.debug("Kill Trash at SEAL B not implemented yet")
                    Logger.debug(seal_layout + "_01: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_01")
                    Logger.debug(seal_layout + "_02: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_02")
                    Logger.debug(seal_layout + "_03: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_03")
                   
                #SEAL
                toggle_automap(False) # just to be safe
                Logger.info(seal_layout +": Starting to pop seals")
                if node_seal1_automap is not None:
                    if not self._pather.traverse_nodes_automap(node_seal1_automap, self._char): return False
                    if not self._sealdance(seal1_opentemplates, seal1_closedtemplates, seal_layout + ": Seal1", node_seal1_automap): return False
                if not self._pather.traverse_nodes_automap(node_seal2_automap, self._char): return False
                if not self._sealdance(seal2_opentemplates, seal2_closedtemplates, seal_layout + ": Seal2", node_seal2_automap): return False
                Logger.debug(seal_layout + ": Kill Boss B (DeSeis)")
                self._char.kill_deseis_automap(seal_layout)
                Logger.debug(seal_layout + ": Traversing back to Pentagram")
                if not self._pather.traverse_nodes_automap([1610], self._char): return False
                Logger.info(seal_layout + ": finished seal & calibrated at PENTAGRAM")   
        
                #Trash B Back to Pent = [1635, 1632, 1638, 1633, 1533, 1610]
        else:
            Logger.debug(f"{seal_layout2}: Layout_check step 1/2 - templates found for {seal_layout2}")
        
            if not confirmation_node2 == None: #cross-check for confirmation
                if not self._pather.traverse_nodes_automap(confirmation_node2, self._char, threshold=calibration_threshold, toggle_map=True): return False
            
            toggle_automap(True)
            pos_m = convert_abs_to_monitor((640, 360)) # move mouse away during LC to not hover items obscuring the minimap
            mouse.move(*pos_m, delay_factor=[0.1, 0.2]) # move mouse away during LC to not hover items obscuring the minimap
            wait(0.25, 0.35)
            if not template_finder.search_and_wait(templates_confirmation, threshold=threshold_confirmation2, timeout=0.2).valid:
                toggle_automap(False)
                Logger.info(f"{seal_layout2}: Layout_check step 2/2 - templates NOT found for "f"{seal_layout1} - "+'\033[96m'+"all fine, proceeding with "f"{seal_layout2}"+'\033[0m')

                ###################
                # Clear Seal B1-S #
                ###################
                
                #Settings
                seal_layout = seal_layout2
                node_seal1_automap=None #Fake
                node_seal2_automap=[1631] #Boss
                seal1_opentemplates=None
                seal1_closedtemplates=None
                seal2_opentemplates=["DIA_B1S2_23_OPEN"]
                seal2_closedtemplates=["DIA_B1S2_23_CLOSED","DIA_B1S2_23_MOUSEOVER"]
                
                #CLEAR TRASH
                if Config().char["dia_kill_trash"]:
                    Logger.info(seal_layout +": Starting to clear seal")
                    Logger.debug("Kill Trash at SEAL B not implemented yet")
                    Logger.debug(seal_layout + "_01: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_01")
                    Logger.debug(seal_layout + "_02: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_02")
                    Logger.debug(seal_layout + "_03: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_03")

                #SEAL
                toggle_automap(False) # just to be safe
                Logger.info(seal_layout +": Starting to pop seals")
                if node_seal1_automap is not None:
                    if not self._pather.traverse_nodes_automap(node_seal1_automap, self._char): return False
                    if not self._sealdance(seal1_opentemplates, seal1_closedtemplates, seal_layout + ": Seal1", node_seal1_automap): return False
                if not self._pather.traverse_nodes_automap(node_seal2_automap, self._char): return False
                if not self._sealdance(seal2_opentemplates, seal2_closedtemplates, seal_layout + ": Seal2", node_seal2_automap): return False
                Logger.debug(seal_layout + ": Kill Boss B (DeSeis)")
                self._char.kill_deseis_automap(seal_layout)
                Logger.debug(seal_layout + ": Traversing back to Pentagram")
                if not self._pather.traverse_nodes_automap([1610], self._char): return False
                Logger.info(seal_layout + ": finished seal & calibrated at PENTAGRAM")

                #Trash B Back to Pent = [1635, 1632, 1638, 1633, 1533, 1610]

            else:
                Logger.warning(f"{seal_layout2}: Layout_check failure - could not determine the seal Layout at " f"{sealname} ("f"{boss}) - "+'\033[91m'+"aborting run"+'\033[0m')
                wait(5)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout2 + "_LC_fail_" + time.strftime("%Y%m%d_%H%M%S") + ".png", grab())
                toggle_automap(True)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout2 + "_LC_fail" + time.strftime("%Y%m%d_%H%M%S") + "automap.png", grab())
                return False
  
        ##########
        # Seal C #
        ##########

        # Settings
        static_layoutcheck = "dia_am_lc_c"
        sealname = "C"
        boss = "Infector"
        seal_layout1= "C1-F"
        seal_layout2= "C2-G"

        calibration_node = [1640]
        calibration_threshold = 0.83
        
        templates_primary= ["DIA_AM_C2G", "DIA_AM_C2G_1", "DIA_AM_C2G_2"]
        threshold_primary= 0.75
                
        templates_confirmation= ["DIA_AM_C1F"]
        confirmation_node= None 
        confirmation_node2=None
        threshold_confirmation= 0.75
        threshold_confirmation2= 0.75

        ###############
        # PREPARATION #
        ###############
        
        #if Config().char["dia_town_visits"]: self._cs_town_visit("A")
        if do_pre_buff and Config().char["dia_kill_trash"]: self._char.pre_buff() #only for dia_kill_trash
        self._char.dia_kill_trash("pent_before_c") # Clear Pentagram

        #############################
        # KILL TRASH TOWARDS SEAL C #
        #############################

        if Config().char["dia_kill_trash"]:
            Logger.debug("CS TRASH: Kill Trash between Pentagram and Layoutcheck C")

            if not self._pather.traverse_nodes_automap([1534], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: trash_to_c1")
            self._char.dia_kill_trash("trash_to_c1")

            if not self._pather.traverse_nodes_automap([1535], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: trash_to_c2")
            self._char.dia_kill_trash("trash_to_c2")

            if not self._pather.traverse_nodes_automap([1536], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: trash_to_c3")
            self._char.dia_kill_trash("trash_to_c3")

            if not self._pather.traverse_nodes_automap([1648], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: approach_c2g")
            self._char.dia_kill_trash("approach_c2g")

            if not self._pather.traverse_nodes_automap([1645], self._char): return False
            Logger.debug("CS TRASH: Killing Trash at: fake_c2g")
            self._char.dia_kill_trash("fake_c2g")

        
        ###############
        # LAYOUTCHECK #
        ###############

        if not self._pather.traverse_nodes_automap(calibration_node, self._char, threshold=calibration_threshold, toggle_map=True): return False
        self._char.dia_kill_trash("layoutcheck_c") # Clear Trash & Loot at Layout Check
        Logger.debug("==============================")
        Logger.debug(f"{sealname}: Checking Layout for "f"{boss}")
        
        if not calibration_node == None:
            if not self._pather.traverse_nodes_automap(calibration_node, self._char, threshold=calibration_threshold,): return False
        
        toggle_automap(True)
        pos_m = convert_abs_to_monitor((640, 360)) # move mouse away during LC to not hover items obscuring the minimap
        mouse.move(*pos_m, delay_factor=[0.1, 0.2]) # move mouse away during LC to not hover items obscuring the minimap
        wait(0.25, 0.35)
        if not template_finder.search_and_wait(templates_primary, threshold =threshold_primary, timeout=0.2).valid: #check1 using primary templates
            toggle_automap(False)
            Logger.debug(f"{seal_layout1}: Layout_check step 1/2 - templates NOT found for "f"{seal_layout2}")
        
            if not confirmation_node == None:#cross-check for confirmation
                if not self._pather.traverse_nodes_automap(confirmation_node, self._char, threshold=calibration_threshold, toggle_map=True): return False
        
            toggle_automap(True)
            pos_m = convert_abs_to_monitor((640, 360)) # move mouse away during LC to not hover items obscuring the minimap
            mouse.move(*pos_m, delay_factor=[0.1, 0.2]) # move mouse away during LC to not hover items obscuring the minimap
            wait(0.25, 0.35)
            if not template_finder.search_and_wait(templates_confirmation, threshold=threshold_confirmation, timeout=0.2).valid:
                toggle_automap(False)
                Logger.warning(f"{seal_layout2}: Layout_check failure - could not determine the seal Layout at " f"{sealname} ("f"{boss}) - "+'\033[91m'+"aborting run"+'\033[0m')
                wait(5)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout1 + "_LC_fail" + time.strftime("%Y%m%d_%H%M%S") + ".png", grab())
                toggle_automap(True)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout1 + "_LC_fail" + time.strftime("%Y%m%d_%H%M%S") + "automap.png", grab())
                return False
        
            else:
                Logger.info(f"{seal_layout1}: Layout_check step 2/2 - templates found for "f"{seal_layout1} - "+'\033[93m'+"all fine, proceeding with "f"{seal_layout1}"+'\033[0m')
                
                ###################
                # Clear Seal C1-F #
                ###################

                #Settings
                seal_layout = seal_layout1
                node_seal1_automap=[1641] #Fake
                node_seal2_automap=[1642] #Boss
                seal1_opentemplates=["DIA_C1F_OPEN_NEAR"]
                seal1_closedtemplates=["DIA_C1F_CLOSED_NEAR","DIA_C1F_MOUSEOVER_NEAR"]
                seal2_opentemplates=["DIA_B2U2_16_OPEN", "DIA_C1F_BOSS_OPEN_RIGHT", "DIA_C1F_BOSS_OPEN_LEFT"]
                seal2_closedtemplates=["DIA_C1F_BOSS_MOUSEOVER_LEFT", "DIA_C1F_BOSS_CLOSED_NEAR_LEFT", "DIA_C1F_BOSS_CLOSED_NEAR_RIGHT"]

                #############################
                # KILL TRASH TOWARDS SEAL C #
                #############################

                #CLEAR TRASH
                if Config().char["dia_kill_trash"]:
                    Logger.info(seal_layout +": Starting to clear seal")
                    Logger.debug("Kill Trash at SEAL C not implemented yet")
                    Logger.debug(seal_layout + "_01: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_01")
                    Logger.debug(seal_layout + "_02: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_02")
                    Logger.debug(seal_layout + "_03: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_03")
               
                #SEAL
                toggle_automap(False) # just to be safe
                Logger.info(seal_layout +": Starting to pop seals")
                if not self._pather.traverse_nodes_automap(node_seal1_automap, self._char): return False
                if not self._sealdance(seal1_opentemplates, seal1_closedtemplates, seal_layout + ": Seal1", node_seal1_automap): return False
                if not self._pather.traverse_nodes_automap(node_seal2_automap, self._char): return False
                if not self._sealdance(seal2_opentemplates, seal2_closedtemplates, seal_layout + ": Seal2", node_seal2_automap): return False
                Logger.debug(seal_layout + ": Kill Boss C (Infector)")
                self._char.kill_infector_automap(seal_layout)
                Logger.debug(seal_layout + ": Traversing back to Pentagram")
                if not self._pather.traverse_nodes_automap([1610], self._char): return False
                Logger.info(seal_layout + ": finished seal & calibrated at PENTAGRAM")     

                #Trash C back to Pent = [1645, 1648, 1536, 1537]

        else:
            Logger.debug(f"{seal_layout2}: Layout_check step 1/2 - templates found for {seal_layout1}")
        
            if not confirmation_node2 == None: #cross-check for confirmation
                if not self._pather.traverse_nodes_automap(confirmation_node2, self._char, threshold=calibration_threshold,): return False
            
            toggle_automap(True)
            pos_m = convert_abs_to_monitor((640, 360)) # move mouse away during LC to not hover items obscuring the minimap
            mouse.move(*pos_m, delay_factor=[0.1, 0.2]) # move mouse away during LC to not hover items obscuring the minimap
            wait(0.25, 0.35)
            if not template_finder.search_and_wait(templates_confirmation, threshold=threshold_confirmation2, timeout=0.2).valid:
                toggle_automap(False)
                Logger.info(f"{seal_layout2}: Layout_check step 2/2 - templates NOT found for "f"{seal_layout1} - "+'\033[96m'+"all fine, proceeding with "f"{seal_layout2}"+'\033[0m')

                ###################
                # Clear Seal C2-G #
                ###################
                
                #Settings
                seal_layout = seal_layout2
                node_seal1_automap=[1645] #Fake
                node_seal2_automap=[1646] #Boss
                seal2_opentemplates=["DIA_C2G2_7_OPEN"]
                seal2_closedtemplates=["DIA_C2G2_7_CLOSED", "DIA_C2G2_7_MOUSEOVER"]
                seal1_opentemplates=["DIA_C2G2_21_OPEN"]
                seal1_closedtemplates=["DIA_C2G2_21_CLOSED", "DIA_C2G2_21_MOUSEOVER"]  
                
                #############################
                # KILL TRASH TOWARDS SEAL C #
                #############################

                #CLEAR TRASH
                if Config().char["dia_kill_trash"]:
                    Logger.info(seal_layout +": Starting to clear seal")
                    Logger.debug("Kill Trash at SEAL C not implemented yet")
                    Logger.debug(seal_layout + "_01: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_01")
                    Logger.debug(seal_layout + "_02: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_02")
                    Logger.debug(seal_layout + "_03: Kill trash")
                    self._char.dia_kill_trash(seal_layout + "_03")

                    #Trash Pent to C LC = [1534, 1535, 1536, 1648, 1645, 1640]

                #SEAL
                toggle_automap(False) # just to be safe
                Logger.info(seal_layout +": Starting to pop seals")
                if not self._pather.traverse_nodes_automap(node_seal1_automap, self._char): return False
                if not self._sealdance(seal1_opentemplates, seal1_closedtemplates, seal_layout + ": Seal1", node_seal1_automap): return False
                if not self._pather.traverse_nodes_automap(node_seal2_automap, self._char): return False
                if not self._sealdance(seal2_opentemplates, seal2_closedtemplates, seal_layout + ": Seal2", node_seal2_automap): return False
                Logger.debug(seal_layout + ": Kill Boss C (Infector)")
                self._char.kill_infector_automap(seal_layout)
                Logger.debug(seal_layout + ": Traversing back to Pentagram")
                if not self._pather.traverse_nodes_automap([1610], self._char): return False
                Logger.info(seal_layout + ": finished seal & calibrated at PENTAGRAM")

                #Trash C back to Pent = [1645, 1648, 1536, 1537]

            else:
                Logger.warning(f"{seal_layout2}: Layout_check failure - could not determine the seal Layout at " f"{sealname} ("f"{boss}) - "+'\033[91m'+"aborting run"+'\033[0m')
                wait(5)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout2 + "_LC_fail_" + time.strftime("%Y%m%d_%H%M%S") + ".png", grab())
                toggle_automap(True)
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_" + seal_layout2 + "_LC_fail" + time.strftime("%Y%m%d_%H%M%S") + "automap.png", grab())
                return False
        
        ##########
        # Diablo #
        ##########
        
        if not self._pather.traverse_nodes_automap([1610], self._char): return False
        
        Logger.info("Waiting for Diablo to spawn")
        
        toggle_automap(False)
        pos_m = convert_abs_to_monitor((640, 360)) # move mouse away during LC to not hover items obscuring the minimap
        mouse.move(*pos_m, delay_factor=[0.1, 0.2]) # move mouse away during LC to not hover items obscuring the minimap
        wait(0.25, 0.35)
        if template_finder.search_and_wait(["DIA_AM_SPAWN", "DIA_AM_CHAT"], threshold=0.85, timeout=0.2).valid:
            Logger.info("Diablo spawn indicator: positive"  + '\033[92m' + " :)" + '\033[0m')
            if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_dia_spawnindicator_positive" + time.strftime("%Y%m%d_%H%M%S") + "automap.png", grab())
            diablo_spawned = True
        else:
            if template_finder.search_and_wait(["DIA_AM_NOSPAWN"], threshold=0.85, timeout=0.2).valid:
                Logger.info("FYI: Diablo spawn indicator: negative" + '\033[91m' + " :(" + '\033[0m')
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_dia_spawnindicator_negative" + time.strftime("%Y%m%d_%H%M%S") + "automap.png", grab())
                diablo_spawned = False
            else:        
                Logger.info("FYI: Diablo spawn indicator: not found - trying to kill anways"  + '\033[43m' + " ???" + '\033[0m')
                if Config().general["info_screenshots"]: cv2.imwrite(f"./log/screenshots/info/info_dia_spawnindicator_notfound" + time.strftime("%Y%m%d_%H%M%S") + "automap.png", grab())
                diablo_spawned = True

        if diablo_spawned:
            self._char.kill_diablo()
            self._picked_up_items |= self._pickit.pick_up_items(char=self._char)
            wait(0.5, 0.7)
            return (Location.A4_DIABLO_END, self._picked_up_items)
        else: 
            return False

        #############
        # TODO LIST #
        #############
        
        # infector C1F is causing too many chicken right now
        # B1S occasionally misses de seis if he spawns far upwards and walks to top (out of vision) - might need to add a second attack pattern here
        # B2U if de seis spawns at new spawn, we miss him.
        # automap shrine detection is broken -> switched templates didnt fix it
        # recalibrate after looting bosses, you get carried away in one direction whilst pickit, losing the second direction if there were mobs
        # implement safe_runs param for seal bosses to walk along the seal (and maybe clear it whilst doing so?)
        # implement river trasverse fixed using charges (or make a chain of "move" commands) - check if maybe we can loop that from WP until CS entrance template is found to avoid fixed path.
        # move mouse away during layout checks to avoid hovering an item that obscures the minimap (implemented, but still occasionally causes a missed seal)
        # consider a name-tag & name-lock for seal bosses & diablo
        # add walkadin pathing (Seal B is teleporting a lot right now)
        # revert back to classical template checks in case the initial check with minimap was bad (merc running around) - or just repeat it by recalibration at LC (hoping the merc goes somewhere else) - or mapcheck through map diff, isolate minimap by waiting a bit between checks, to isolate movement (E.g. merc)