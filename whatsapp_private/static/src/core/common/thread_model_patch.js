import {fields} from "@mail/core/common/record";
import {Thread} from "@mail/core/common/thread_model";
import {patch} from "@web/core/utils/patch";

patch(Thread.prototype, {
    setup() {
        super.setup();
        this.whatsapp_auto_open_chat_window = fields.Attr();
    },
    get autoOpenChatWindowOnNewMessage() {
        if (
            this.channel_type === "whatsapp" &&
            this.whatsapp_auto_open_chat_window === false
        ) {
            return false;
        }
        return super.autoOpenChatWindowOnNewMessage;
    },
    /* Muted whatsapp threads must not spawn a folded chat window either,
       otherwise a chat bubble still pops up in the ChatHub. */
    get inChathubOnNewMessage() {
        if (
            this.channel_type === "whatsapp" &&
            this.whatsapp_auto_open_chat_window === false
        ) {
            return false;
        }
        return super.inChathubOnNewMessage;
    },
});
