User docs
=========

Everything is a MUC
-------------------

Direct channels rooms (1:1 messages) appear as "unnamed rooms".

E2EE
----

End-to-end encryption is not possible, but you can use end-to-bridge encryption.
First, verify your slidge session using another client;
it is a bit buried down in Element for some reason.
Open any of your rooms, look for yourself in the members list, then
you will be able to verify your slidge session. (the "normal" way of verifying
with emojis is not supported ATM).

Then you will have to either "verify", "ignore", or "blacklist" the keys
corresponding to your rooms and your other sessions.
This can be done using the adhoc or chat command "verify" (send "verify" to
the JID of matridge, eg ``matridge.example.com``.
If you don't really care about all this, you can use the shortcut "verify all".
