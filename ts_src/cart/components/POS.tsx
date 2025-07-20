import * as React from "react";
import {FormEvent, useCallback, useEffect, useRef, useState} from "react";
import * as path from "path";

import {IPOSProps, IUser} from "../interfaces";
import POSPayment from "./POSPayment"
import CartBody from "./CartBody";
import CartSelector from "./CartSelector";
import {RootState, useAppDispatch} from "../store";
import {addCustomPOSItem, addNewPOSItem, clearPOSOwner, errorsClear, setPOS, setPOSOwner,} from "../reducers/cartSlice";
import {useSelector} from "react-redux";
import {Autocomplete, TextField} from "@mui/material";
import getCookie from "./get_cookie";
import {useDebounce} from 'usehooks-ts'


const POS: React.FunctionComponent<IPOSProps> = (props: IPOSProps): JSX.Element => {
    const dispatch = useAppDispatch();
    const currentStatus = useSelector((state: RootState) => state.cart.pos);
    const errors = useSelector((state: RootState) => state.cart.errors);
    const [currentEmail, setCurrentEmail] = useState<string>('')
    const debouncedEmailString = useDebounce<string>(currentEmail, 500)
    const [userSuggestions, setUserSuggestions] = useState<IUser[]>([])
    const emailFieldRef = useRef();

    const [showCost, setShowCost] = useState<boolean>(false)

    const toggleCost = useCallback(() => {
        setShowCost(!showCost)
    }, [showCost])

    const ordersURL = path.normalize(path.join(props.url, '..'));
    console.log(ordersURL)

    useEffect(() => {
        dispatch(setPOS(props));
    }, [props]);


    React.useEffect(() => {
        if (currentStatus.active_cart && currentStatus.active_cart.id) {
            window.history.replaceState(
                null,
                "",
                `${currentStatus.url}/${currentStatus.active_cart.id}/`
            );
        }
        console.log("Selected cart changed!")

        if (emailFieldRef.current) {
            //https://github.com/mui/material-ui/issues/4736
            const field = emailFieldRef.current as HTMLInputElement;
            const clearButton = field.getElementsByClassName('MuiAutocomplete-clearIndicator')[0] as HTMLButtonElement;
            if (clearButton) {
                clearButton.click();
                console.log("Attempted to clear the field")

            }

        }
    }, [currentStatus.active_cart]);

    const HandleScan = (event: CustomEvent) => { // Alternative to document.addEventListener('scan')
        let sCode = event.detail.scanCode
        AddItem(sCode)

    }

    const HandleAdd = (event: FormEvent) => {
        event.preventDefault()
        const data = new FormData(event.target as HTMLFormElement);
        AddItem(data.get('barcode') as string);
        (event.target as HTMLFormElement).reset()

    }


    const AddItem = (barcode: string) => {
        if (barcode.trim() == "") {
            return
        }
        dispatch(
            addNewPOSItem({
                barcode,
            })
        );
    }

    const HandleCustom = (event: FormEvent) => {
        event.preventDefault()
        const data = new FormData(event.target as HTMLFormElement);
        dispatch(
            addCustomPOSItem({
                description: data.get("description") as string,
                price: Number(data.get("price") as string),
            })
        );
        (event.target as HTMLFormElement).reset()
    }


    const HandleOwner = (event: FormEvent) => {
        event.preventDefault()
        const data = new FormData(event.target as HTMLFormElement);
        const raw_str = data.get("email") as string
        //The raw string could be a value from the dropdown.
        const email = raw_str.includes(" ") ? raw_str.split(" ")[0] : raw_str;
        dispatch(
            setPOSOwner({
                email: email,
            })
        );
        (event.target as HTMLFormElement).reset()
    }

    const HandleClearOwner = () => {
        dispatch(clearPOSOwner())
    }

    const handleEmailChange = (event: React.SyntheticEvent, value: string, reason: string) => {
        console.log(reason)
        setCurrentEmail(value)
    }
    useEffect(() => {
        const value = debouncedEmailString
        if (value) {
            fetch(
                `${currentStatus.url}/${currentStatus.active_cart.id}/suggest_owner/`,
                {
                    method: "post",
                    body: JSON.stringify({
                        email: value,
                    }),
                    headers: {"X-CSRFToken": getCookie("csrftoken")},
                })
                .then(function (response) {
                    return response.json();
                })
                .then(function (myJson) {
                    console.log(
                        "search term: " + value + ", results: ", myJson.users
                    );
                    const updatedOptions = myJson.users.map((p: IUser) => {
                        return {label: p.email + " - " + p.username, email: p.email};
                    });
                    setUserSuggestions(updatedOptions);
                });
        } else {
            setUserSuggestions([]);
        }
    }, [debouncedEmailString]);

    React.useEffect(() => {
        document.addEventListener('scan', HandleScan)
        return function cleanup() {
            document.removeEventListener("scan", HandleScan);
        }
    }, [HandleScan]); // <--- This hook is called only once


    const error_section = errors.length > 0 ? <div>
        <ul> Errors:
            {errors.map((error: String) => {
                return <li><h3>{error}</h3></li>
            })}
        </ul>
        <button onClick={() => dispatch(errorsClear())} className={'btn btn-danger'}>Clear Errors</button>
    </div> : null

    return (
        <>
            {error_section}
            <div className="flex flex-row">
                <div>
                    <POSPayment
                        base_url={props.url}
                        cart={currentStatus.active_cart}
                    />
                    <CartSelector/>
                </div>
                <div>
                    {currentStatus.active_cart &&
                    currentStatus.active_cart.id ? (
                        <>
                            <h1>
                                {" "}
                                Cart Number: {currentStatus.active_cart.open ?
                                currentStatus.active_cart.id :
                                <a href={path.join(ordersURL, currentStatus.active_cart.id.toString())}>{currentStatus.active_cart.id}</a>
                            }
                                <input type={"number"} step='1' id={'id_cart_id'} hidden={true} readOnly={true}
                                       value={currentStatus.active_cart.id}>
                                </input>
                            </h1>
                            {currentStatus.active_cart.status}
                            <form onSubmit={HandleOwner}>
                                <Autocomplete ref={emailFieldRef}
                                              freeSolo
                                              onInputChange={handleEmailChange}
                                              options={userSuggestions}
                                              filterOptions={(x) => x}
                                              renderInput={(params) => <TextField {...params} name="email"
                                                                                  label="Email"/>}
                                />
                                <input type="submit" value="Set" className="btn btn-secondary"/>
                                <button onClick={HandleClearOwner} className="btn btn-warning">Clear</button>
                            </form>


                            <p>
                                Owner:{" "} {currentStatus.active_cart.owner_info}
                            </p>
                            {["Open", "Submitted"].includes(currentStatus.active_cart.status) ? (
                                <>
                                    <form onSubmit={HandleAdd}>
                                        <h3>Add Item (Or Scan):</h3>
                                        <label>
                                            Barcode:
                                            <input type="text" name="barcode"/>
                                        </label>
                                        <input type="submit" value="Add" className="btn btn-secondary"/>
                                    </form>
                                    <form onSubmit={HandleCustom}>
                                        <h3>Add Custom Item:</h3>
                                        <label>
                                            Description:
                                            <input
                                                type="text"
                                                name="description"
                                            />
                                        </label>
                                        <label>
                                            Price:
                                            <input
                                                type="number"
                                                name="price"
                                                step=".01"
                                            />
                                        </label>
                                        <input type="submit" value="Add" className="btn btn-secondary"/>
                                    </form>
                                </>
                            ) : (
                                <></>
                            )}
                            <button onClick={toggleCost}
                                    className="btn btn-secondary">{showCost ? "Hide Cost" : "Show Cost"}</button>
                            <CartBody
                                cart={currentStatus.active_cart}
                                full={true}
                                pos={true}
                                showCost={showCost}
                            />
                        </>
                    ) : (
                        <></>
                    )}
                </div>
            </div>
        </>
    );
};

export default POS
