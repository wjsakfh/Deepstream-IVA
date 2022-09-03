from typing import List
from dto.Obj import PgieObj


class BaseAlarmGenerator:
    obj_list: List

    def run(self):
        pass


class IntrusionAlarmGenerator(BaseAlarmGenerator):
    def __init__(self, obj_list: List[PgieObj]):
        self.obj_list = obj_list

    def run(self):
        for obj in self.obj_list:
            flag_list = obj.intrusion_flag_list
            first_flag, last_flag = self.__get_flag(flag_list)
            if first_flag == True and last_flag == False:
                print(obj.obj_id, "Intrusion Finish")
            elif first_flag == False and last_flag == True:
                print(obj.obj_id, "Intrusion Start")
            elif first_flag == True and last_flag == True:
                print(obj.obj_id, "Intrusion")
            else:
                print(obj.obj_id, "")

    def __get_flag(self, flag_list):
        half_length = int(len(flag_list) * 0.5)
        first_list = flag_list[:half_length]
        last_list = flag_list[half_length:]
        first_flag = (
            True if first_list.count(True) >= first_list.count(False) else False
        )
        last_flag = True if last_list.count(True) >= last_list.count(False) else False

        return first_flag, last_flag
