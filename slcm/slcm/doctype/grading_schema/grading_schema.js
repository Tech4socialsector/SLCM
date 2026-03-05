// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Grading Schema", {
    refresh: function (frm) {
        // pass
    }
});

frappe.ui.form.on("Grading Schema Component", {
    grade: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.grade) {
            let formatted_grade = format_superscript_subscript(row.grade);
            if (formatted_grade !== row.grade) {
                frappe.model.set_value(cdt, cdn, "grade", formatted_grade);
            }
        }
    }
});

function format_superscript_subscript(text) {
    const sup_map = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
        '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
        'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ',
        'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ',
        'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ', 'o': 'ᵒ',
        'p': 'ᵖ', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ',
        'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ'
    };
    const sub_map = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
        '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
        '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
        'a': 'ₐ', 'e': 'ₑ', 'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ',
        'k': 'ₖ', 'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ',
        'p': 'ₚ', 'r': 'ᵣ', 's': 'ₛ', 't': 'ₜ', 'u': 'ᵤ',
        'v': 'ᵥ', 'x': 'ₓ'
    };

    // Convert HTML tags if pasted
    text = text.replace(/<sup>(.*?)<\/sup>/gi, function (match, p1) {
        return Array.from(p1).map(c => sup_map[c] || c).join('');
    });
    text = text.replace(/<sub>(.*?)<\/sub>/gi, function (match, p1) {
        return Array.from(p1).map(c => sub_map[c] || c).join('');
    });

    // Automatically convert standard '+' and '-' to superscript if they follow a letter/number
    text = text.replace(/([A-Z0-9a-z])\+/g, '$1⁺');
    text = text.replace(/([A-Z0-9a-z])-/g, '$1⁻');

    let result = '';
    for (let i = 0; i < text.length; i++) {
        if (text[i] === '^' && i + 1 < text.length && sup_map[text[i + 1]]) {
            result += sup_map[text[i + 1]];
            i++;
        } else if (text[i] === '_' && i + 1 < text.length && sub_map[text[i + 1]]) {
            result += sub_map[text[i + 1]];
            i++;
        } else {
            // If they just typed a trailing ^ or _, let's ignore it or leave it as is.
            // To avoid annoyance if they type A_ and tab out, let's leave it.
            result += text[i];
        }
    }

    return result;
}
