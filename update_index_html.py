import re

with open('/home/bsoft/frappe16-bench/apps/slcm/slcm/www/pace/index.html', 'r') as f:
    content = f.read()

# Replace the form inside pace-inquiry-card
old_form = """                            <form class="space-y-8">
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-10">
                                    <div class="relative group">
                                        <input
                                            class="peer w-full border-b-2 border-surface-variant/40 bg-transparent py-3 focus:outline-none focus:border-primary transition-all text-lg placeholder-transparent input-transition"
                                            id="full-name" placeholder=" " type="text" />
                                        <label
                                            class="absolute left-0 top-3 text-on-surface/40 text-[10px] font-bold uppercase tracking-widest transition-all peer-focus:-top-4 peer-focus:text-primary peer-[:not(:placeholder-shown)]:-top-4"
                                            for="full-name">Full name</label>
                                    </div>
                                    <div class="relative group">
                                        <input
                                            class="peer w-full border-b-2 border-surface-variant/40 bg-transparent py-3 focus:outline-none focus:border-primary transition-all text-lg placeholder-transparent input-transition"
                                            id="email" placeholder=" " type="email" />
                                        <label
                                            class="absolute left-0 top-3 text-on-surface/40 text-[10px] font-bold uppercase tracking-widest transition-all peer-focus:-top-4 peer-focus:text-primary peer-[:not(:placeholder-shown)]:-top-4"
                                            for="email">Email address</label>
                                    </div>
                                </div>
                                <div class="relative group">
                                    <input
                                        class="peer w-full border-b-2 border-surface-variant/40 bg-transparent py-3 focus:outline-none focus:border-primary transition-all text-lg placeholder-transparent input-transition"
                                        id="phone" placeholder=" " type="tel" />
                                    <label
                                        class="absolute left-0 top-3 text-on-surface/40 text-[10px] font-bold uppercase tracking-widest transition-all peer-focus:-top-4 peer-focus:text-primary peer-[:not(:placeholder-shown)]:-top-4"
                                        for="phone">Phone number</label>
                                </div>
                                <div class="relative group">
                                    <label
                                        class="block text-[10px] font-bold uppercase tracking-[0.2em] mb-2 pace-inquiry-select-label">Programme
                                        of interest</label>
                                    <div class="relative">
                                        <select
                                            class="w-full border-b-2 border-surface-variant/40 bg-transparent py-3 focus:outline-none focus:border-primary transition-all text-lg appearance-none cursor-pointer pr-10 input-transition">
                                            <option>Master of Business Laws (MBL)</option>
                                            <option>PG Diploma in Cyber Law</option>
                                            <option>PG Diploma in IP Rights</option>
                                            <option>PG Diploma in Environmental Law</option>
                                        </select>
                                        <span
                                            class="material-symbols-outlined absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none text-on-surface/40">expand_more</span>
                                    </div>
                                </div>
                                <div class="pt-6">
                                    <button
                                        class="w-full bg-primary text-white py-5 font-label text-xs font-bold uppercase tracking-[0.3em] transition-all hover:bg-primary-container hover:shadow-2xl hover:-translate-y-1 active:translate-y-0 shadow-lg"
                                        type="submit">
                                        Submit Request
                                    </button>
                                </div>
                            </form>"""

new_form = """                            <form class="space-y-6">
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    <div class="space-y-2">
                                        <label class="block text-[10px] font-bold uppercase tracking-[0.15em] text-[#a1a1aa]" for="full-name">Full Name</label>
                                        <input class="w-full border-b border-[#e4e4e7] bg-transparent py-2 focus:outline-none focus:border-primary transition-all pb-3" id="full-name" type="text" />
                                    </div>
                                    <div class="space-y-2">
                                        <label class="block text-[10px] font-bold uppercase tracking-[0.15em] text-[#a1a1aa]" for="email">Email Address</label>
                                        <input class="w-full border-b border-[#e4e4e7] bg-transparent py-2 focus:outline-none focus:border-primary transition-all pb-3" id="email" type="email" />
                                    </div>
                                </div>
                                <div class="space-y-2 pt-2">
                                    <label class="block text-[10px] font-bold uppercase tracking-[0.15em] text-[#a1a1aa]" for="phone">Phone Number</label>
                                    <input class="w-full border-b border-[#e4e4e7] bg-transparent py-2 focus:outline-none focus:border-primary transition-all pb-3" id="phone" type="tel" />
                                </div>
                                <div class="space-y-2 pt-2">
                                    <label class="block text-[10px] font-bold uppercase tracking-[0.15em] pb-1" style="color: var(--primary);" for="programme">Programme of Interest</label>
                                    <div class="relative">
                                        <select class="w-full border-b border-[#e4e4e7] bg-transparent py-2 focus:outline-none focus:border-primary transition-all text-base text-[#3f3f46] appearance-none cursor-pointer pr-10 pb-3" id="programme">
                                            <option>Master of Business Laws (MBL)</option>
                                            <option>PG Diploma in Cyber Law</option>
                                            <option>PG Diploma in IP Rights</option>
                                            <option>PG Diploma in Environmental Law</option>
                                        </select>
                                        <span class="material-symbols-outlined absolute right-0 top-[30%] pointer-events-none text-[#a1a1aa] text-xl">expand_more</span>
                                    </div>
                                </div>
                                <div class="pt-6">
                                    <button class="w-full py-4 font-label text-[11px] font-bold uppercase tracking-[0.25em] transition-all hover:opacity-90 active:scale-[0.99] shadow-sm rounded-sm" style="background-color: var(--primary); color: white;" type="submit">
                                        Submit Request
                                    </button>
                                </div>
                            </form>"""

content = content.replace(old_form, new_form)

# Add font size inline to the p tag to match design
content = content.replace(
    '<p class="text-on-surface-variant mb-10 text-lg font-light">Complete the form below and our',
    '<p class="text-on-surface-variant mb-10 font-light" style="font-size: 1.05rem;">Complete the form below and our'
)

with open('/home/bsoft/frappe16-bench/apps/slcm/slcm/www/pace/index.html', 'w') as f:
    f.write(content)

