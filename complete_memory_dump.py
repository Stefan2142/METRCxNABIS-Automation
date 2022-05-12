def memory_dump():
    """
    List all the local variables in each stack frame.
    """
    tb = sys.exc_info()[2]
    while 1:
        if not tb.tb_next:
            break
        tb = tb.tb_next
    stack = []
    f = tb.tb_frame
    while f:
        stack.append(f)
        f = f.f_back
    # stack.reverse()

    dump = ""
    dump += traceback.format_exc() + "\n"

    dump += "Locals by frame:\n"
    fl_name = dt.datetime.now().strftime("%Y-%m-%d_%H_%M")
    for frame in stack[:]:
        dump += "Frame %s in %s at line %s" % (
            frame.f_code.co_name,
            frame.f_code.co_filename,
            frame.f_lineno,
        )
        for key, value in frame.f_locals.items():

            dump += "\t%20s = " % key
            # We have to be VERY careful not to cause a new error in our error
            # printer! Calling str(  ) on an unknown object could cause an
            # error we don't want, so we must use try/except to catch it --
            # we can't stop it from happening, but we can and should
            # stop it from propagating if it does happen!
            try:
                # print("DUMP:", sys.getsizeof(dump))
                # print("DUMP:", sys.getsizeof(value))
                dump += f"{value}\n"
            except:
                dump += "<ERROR WHILE GETTING VALUE>\n"
    with open(f"{paths['logs']}Dump_{fl_name}.txt", "w") as f:
        f.write(dump)
