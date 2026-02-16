// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("University", {
    refresh(frm) {

    },

    university_name: function (frm) {
        if (!frm.doc.university_name) {
            frm.set_value("abbr", "");
            return;
        }

        // Clean special characters
        let clean_name = frm.doc.university_name.replace(/[^A-Za-z0-9 ]+/g, "");

        // Words to ignore
        let ignore_words = ["of", "the", "and", "&"];

        let words = clean_name.split(" ");

        // Generate abbreviation
        let abbr = words
            .filter(word => word && !ignore_words.includes(word.toLowerCase()))
            .map(word => word[0].toUpperCase())
            .join("");

        frm.set_value("abbr", abbr);
    }
});
