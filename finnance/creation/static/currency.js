function update_currency(input_selector, d, zero=false, positive=true) {
    console.log('start');
    const step = Math.pow(10, -d);
    $(input_selector).each(function () {
        let val = parseFloat($(this).val());
        $(this).prop({
            "step": step,
            "value": (zero || isNaN(val)) ? 
                0 : val.toFixed(d),
            "min": positive ? step : 0
        });
    });
    let inputs = document.querySelectorAll(input_selector);
    for (let inp of inputs) {
        let sub = inp.nextElementSibling;
        if (sub != null && sub.tagName == "SMALL") {
            sub.innerHTML = (positive ? "positive" : "non-negative") + ", " + (d == 0 ? "no" : `up to ${d}`) + " decimals";
        }
    }
}