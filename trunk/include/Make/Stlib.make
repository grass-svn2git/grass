
STLIB = $(ARCH_LIBDIR)/$(STLIB_PREFIX)$(STLIB_NAME)$(STLIB_SUFFIX)

$(STLIB): $(STLIB_OBJS)
	$(STLIB_LD) $@ $?; $(RANLIB) $@

stlib: $(STLIB)

