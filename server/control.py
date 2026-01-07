_door_controller = None


def set_door_controller(controller):
    global _door_controller
    _door_controller = controller


def get_door_controller():
    return _door_controller
